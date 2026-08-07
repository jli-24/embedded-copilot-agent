from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Protocol

from embedded_copilot.workspace_runtime.approval import ApprovalContext, ApprovalStatus
from embedded_copilot.workspace_runtime.audit import applied_audit
from embedded_copilot.workspace_runtime.filesystem import (
    WorkspaceFileInvalid,
    assert_workspace_file_identity,
    read_workspace_file,
)
from embedded_copilot.workspace_runtime.models import (
    ApplyResult,
    ApplyStatus,
    ChangeProposal,
    FrozenWorkspaceSnapshot,
    ValidationResult,
    ValidationStatus,
    WorkspaceAuditEvent,
    WorkspaceInspectionRequest,
)
from embedded_copilot.workspace_runtime.ports import WorkspacePort
from embedded_copilot.workspace_runtime.validator import (
    PatchValidator,
    PreparedChange,
    PreparedFileChange,
)


class _FileWritePort(Protocol):
    def apply(
        self, change: PreparedChange, approval: ApprovalContext
    ) -> WorkspaceAuditEvent: ...


class _WorkspaceChangedDuringWrite(OSError):
    pass


class _WriteFailed(OSError):
    pass


class _RollbackFailed(OSError):
    pass


class _PrivateFileWriteFailed(OSError):
    def __init__(self, *, artifact_remains: bool) -> None:
        super().__init__("private workspace artifact write failed")
        self.artifact_remains = artifact_remains


class _SecureFileWritePort:
    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    def apply(
        self, change: PreparedChange, approval: ApprovalContext
    ) -> WorkspaceAuditEvent:
        artifacts: list[_WriteArtifact] = []
        replaced: list[_WriteArtifact] = []
        try:
            for item in change.files:
                self._preflight(item)
                artifact = self._artifact(change, item)
                artifacts.append(artifact)
                self._prepare_artifact(artifact)
            for artifact in artifacts:
                self._preflight(artifact.change)
            for artifact in artifacts:
                self._preflight(artifact.change)
                os.replace(artifact.temporary, artifact.target)
                artifact.temporary_owned = False
                replaced.append(artifact)
        except WorkspaceFileInvalid:
            self._rollback_or_raise(artifacts, replaced)
            raise _WorkspaceChangedDuringWrite from None
        except OSError:
            self._rollback_or_raise(artifacts, replaced)
            raise _WriteFailed from None
        self._remove_backups_or_rollback(artifacts, replaced)
        return applied_audit(
            proposal_id=change.proposal.proposal_id,
            workspace_id=change.snapshot.workspace_id,
            files=change.proposal.target_files,
            approval=approval,
        )

    def _preflight(self, item: PreparedFileChange) -> None:
        current = read_workspace_file(self._root, item.relative_path)
        if (
            current.content != item.before
            or current.identity.stable_key() != item.identity.stable_key()
            or current.parent_identities != item.parent_identities
        ):
            raise WorkspaceFileInvalid("workspace file changed")
        assert_workspace_file_identity(
            self._root,
            item.relative_path,
            item.identity,
            item.parent_identities,
        )

    def _artifact(
        self, change: PreparedChange, item: PreparedFileChange
    ) -> "_WriteArtifact":
        target = self._root.joinpath(*item.relative_path.split("/"))
        token = hashlib.sha256(
            (
                change.proposal.proposal_id
                + "\x00"
                + change.snapshot.snapshot_fingerprint
                + "\x00"
                + item.relative_path
            ).encode("utf-8")
        ).hexdigest()[:20]
        temporary = target.with_name(f".{target.name}.workspace-{token}.tmp")
        backup = target.with_name(f".{target.name}.workspace-{token}.bak")
        return _WriteArtifact(
            change=item,
            target=target,
            temporary=temporary,
            backup=backup,
        )

    def _prepare_artifact(self, artifact: "_WriteArtifact") -> None:
        try:
            _write_private_file(
                artifact.temporary,
                artifact.change.after,
                artifact.change.identity.mode,
            )
        except _PrivateFileWriteFailed as exc:
            artifact.temporary_owned = exc.artifact_remains
            raise
        artifact.temporary_owned = True
        try:
            _write_private_file(
                artifact.backup,
                artifact.change.before,
                artifact.change.identity.mode,
            )
        except _PrivateFileWriteFailed as exc:
            artifact.backup_owned = exc.artifact_remains
            raise
        artifact.backup_owned = True

    def _rollback_or_raise(
        self,
        artifacts: list["_WriteArtifact"],
        replaced: list["_WriteArtifact"],
    ) -> None:
        failed = False
        for artifact in reversed(replaced):
            if not artifact.backup_owned:
                failed = True
                continue
            try:
                os.replace(artifact.backup, artifact.target)
                artifact.backup_owned = False
            except OSError:
                failed = True
        for artifact in artifacts:
            if artifact.temporary_owned:
                try:
                    _unlink_if_present(artifact.temporary)
                    artifact.temporary_owned = False
                except OSError:
                    failed = True
        if failed:
            raise _RollbackFailed from None
        for artifact in artifacts:
            if artifact.backup_owned:
                try:
                    _unlink_if_present(artifact.backup)
                    artifact.backup_owned = False
                except OSError:
                    failed = True
        if failed:
            raise _RollbackFailed from None

    def _remove_backups_or_rollback(
        self,
        artifacts: list["_WriteArtifact"],
        replaced: list["_WriteArtifact"],
    ) -> None:
        removed: list[_WriteArtifact] = []
        try:
            for artifact in artifacts:
                if artifact.backup_owned:
                    artifact.backup.unlink()
                    artifact.backup_owned = False
                    removed.append(artifact)
        except OSError:
            for artifact in removed:
                try:
                    _write_private_file(
                        artifact.backup,
                        artifact.change.before,
                        artifact.change.identity.mode,
                    )
                except _PrivateFileWriteFailed as exc:
                    artifact.backup_owned = exc.artifact_remains
                    raise _RollbackFailed from None
                artifact.backup_owned = True
            self._rollback_or_raise(artifacts, replaced)
            raise _WriteFailed from None


class _WriteArtifact:
    __slots__ = (
        "backup",
        "backup_owned",
        "change",
        "target",
        "temporary",
        "temporary_owned",
    )

    def __init__(
        self,
        *,
        change: PreparedFileChange,
        target: Path,
        temporary: Path,
        backup: Path,
    ) -> None:
        self.change = change
        self.target = target
        self.temporary = temporary
        self.backup = backup
        self.temporary_owned = False
        self.backup_owned = False


class _WorkspacePort:
    __slots__ = (
        "_root",
        "_snapshots",
        "_validated_proposals",
        "_validator",
        "_writer",
    )

    def __init__(self, root: Path, writer: _FileWritePort) -> None:
        self._root = root
        self._snapshots: dict[str, FrozenWorkspaceSnapshot] = {}
        self._validated_proposals: dict[str, str] = {}
        self._validator = PatchValidator(root)
        self._writer = writer

    def inspect_workspace(
        self, request: WorkspaceInspectionRequest
    ) -> FrozenWorkspaceSnapshot:
        request = WorkspaceInspectionRequest.model_validate(request)
        snapshot = self._validator.inspect(request)
        self._snapshots[snapshot.snapshot_fingerprint] = snapshot
        return snapshot

    def validate_change(self, proposal: ChangeProposal) -> ValidationResult:
        proposal = ChangeProposal.model_validate(proposal)
        result, _ = self._validation(proposal)
        if result.status is ValidationStatus.WAITING_APPROVAL:
            fingerprint = _proposal_fingerprint(proposal)
            previous = self._validated_proposals.get(proposal.proposal_id)
            if previous is not None and previous != fingerprint:
                return ValidationResult(
                    status=ValidationStatus.REJECTED,
                    proposal_id=proposal.proposal_id,
                    workspace_id=result.workspace_id,
                    workspace_snapshot_id=result.workspace_snapshot_id,
                    target_files=proposal.target_files,
                    error_code="proposal_conflict",
                )
            self._validated_proposals[proposal.proposal_id] = fingerprint
        return result

    def apply_change(
        self, proposal: ChangeProposal, approval: ApprovalContext
    ) -> ApplyResult:
        proposal = ChangeProposal.model_validate(proposal)
        approval = ApprovalContext.model_validate(approval)
        result, prepared = self._validation(proposal)
        if result.status is not ValidationStatus.WAITING_APPROVAL or prepared is None:
            if result.status is ValidationStatus.WORKSPACE_CHANGED:
                return _rejected_apply(result, "workspace_changed")
            return _rejected_apply(result, "validation_rejected")
        if self._validated_proposals.get(proposal.proposal_id) != _proposal_fingerprint(
            proposal
        ):
            return _rejected_apply(result, "approval_required")
        if not _approval_matches(proposal, prepared.snapshot, approval):
            return _rejected_apply(result, "approval_required")
        try:
            audit = self._writer.apply(prepared, approval)
        except _WorkspaceChangedDuringWrite:
            return _rejected_apply(result, "workspace_changed")
        except _RollbackFailed:
            self._validated_proposals.pop(proposal.proposal_id, None)
            return _rejected_apply(result, "rollback_failed")
        except _WriteFailed:
            return _rejected_apply(result, "write_failed")
        applied = ApplyResult(
            status=ApplyStatus.APPLIED,
            proposal_id=proposal.proposal_id,
            workspace_id=prepared.snapshot.workspace_id,
            target_files=proposal.target_files,
            audit_event=audit,
        )
        self._validated_proposals.pop(proposal.proposal_id, None)
        return applied

    def _validation(
        self, proposal: ChangeProposal
    ) -> tuple[ValidationResult, PreparedChange | None]:
        snapshot = self._snapshots.get(proposal.workspace_snapshot_id)
        if snapshot is None:
            return (
                ValidationResult(
                    status=ValidationStatus.REJECTED,
                    proposal_id=proposal.proposal_id,
                    workspace_id="workspace:unknown",
                    workspace_snapshot_id=proposal.workspace_snapshot_id,
                    target_files=proposal.target_files,
                    error_code="snapshot_unknown",
                ),
                None,
            )
        return self._validator.validate(proposal, snapshot)


def _approval_matches(
    proposal: ChangeProposal,
    snapshot: FrozenWorkspaceSnapshot,
    approval: ApprovalContext,
) -> bool:
    return (
        approval.status is ApprovalStatus.APPROVED
        and approval.proposal_id == proposal.proposal_id
        and approval.workspace_id == snapshot.workspace_id
        and approval.workspace_snapshot_id == snapshot.snapshot_fingerprint
        and approval.target_files == proposal.target_files
    )


def _rejected_apply(result: ValidationResult, code: str) -> ApplyResult:
    return ApplyResult(
        status=ApplyStatus.REJECTED,
        proposal_id=result.proposal_id,
        workspace_id=result.workspace_id,
        target_files=result.target_files,
        error_code=code,
    )


def _proposal_fingerprint(proposal: ChangeProposal) -> str:
    encoded = json.dumps(
        proposal.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class WorkspaceRuntime:
    __slots__ = ("_workspace_port",)

    def __init__(self, workspace_port: WorkspacePort) -> None:
        raise TypeError("WorkspaceRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, workspace_port: WorkspacePort) -> "WorkspaceRuntime":
        if not isinstance(workspace_port, WorkspacePort):
            raise TypeError("workspace port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_workspace_port", workspace_port)
        return runtime

    def workspace_port(self) -> WorkspacePort:
        return self._workspace_port


def create_workspace_runtime(workspace_root: Path) -> WorkspaceRuntime:
    if not isinstance(workspace_root, Path):
        raise TypeError("workspace root is invalid")
    if workspace_root.is_symlink():
        raise ValueError("workspace root is invalid")
    root = workspace_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace root is invalid")
    return WorkspaceRuntime._compose(_WorkspacePort(root, _SecureFileWritePort(root)))


def _write_private_file(path: Path, content: bytes, mode: int) -> None:
    created = False
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, stat.S_IMODE(mode))
    except OSError:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        artifact_remains = created
        if created:
            try:
                path.unlink()
            except OSError:
                pass
            else:
                artifact_remains = False
        raise _PrivateFileWriteFailed(artifact_remains=artifact_remains) from None


def _unlink_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
