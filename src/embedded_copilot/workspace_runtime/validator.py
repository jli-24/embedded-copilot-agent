from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from embedded_copilot.workspace_runtime.filesystem import (
    DirectoryIdentity,
    FileIdentity,
    MAX_WORKSPACE_FILE_SIZE,
    ValidatedWorkspaceFile,
    WorkspaceFileInvalid,
    read_workspace_file,
)
from embedded_copilot.workspace_runtime.models import (
    ChangeProposal,
    FrozenWorkspaceSnapshot,
    ValidationResult,
    ValidationStatus,
    WorkspaceFileSummary,
    WorkspaceInspectionRequest,
    WorkspaceLanguage,
)
from embedded_copilot.workspace_runtime.snapshot import build_snapshot

_DIFF_HEADER = re.compile(r"^diff --git a/([^\s]+) b/([^\s]+)$")
_OLD_HEADER = re.compile(r"^--- a/(.+)$")
_NEW_HEADER = re.compile(r"^\+\+\+ b/(.+)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@$")


@dataclass(frozen=True)
class PreparedFileChange:
    relative_path: str
    before: bytes
    after: bytes
    identity: FileIdentity
    parent_identities: tuple[DirectoryIdentity, ...]


@dataclass(frozen=True)
class PreparedChange:
    proposal: ChangeProposal
    snapshot: FrozenWorkspaceSnapshot
    files: tuple[PreparedFileChange, ...]


class PatchValidator:
    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    def inspect(self, request: WorkspaceInspectionRequest) -> FrozenWorkspaceSnapshot:
        files = tuple(
            sorted(
                (self._summary(path) for path in request.relative_paths),
                key=lambda item: item.relative_path.casefold(),
            )
        )
        return build_snapshot(workspace_id=request.workspace_id, files=files)

    def validate(
        self, proposal: ChangeProposal, snapshot: FrozenWorkspaceSnapshot
    ) -> tuple[ValidationResult, PreparedChange | None]:
        if proposal.workspace_snapshot_id != snapshot.snapshot_fingerprint:
            return self._rejected(proposal, snapshot, "snapshot_unknown")
        snapshot_files = {item.relative_path: item for item in snapshot.files}
        if not set(proposal.target_files) <= set(snapshot_files):
            return self._rejected(proposal, snapshot, "invalid_diff")
        current = self._current_files(proposal, snapshot_files)
        if current is None:
            return self._changed(proposal, snapshot)
        try:
            prepared = self._prepare(proposal, snapshot, current)
        except _InvalidText:
            return self._rejected(proposal, snapshot, "invalid_text")
        except ValueError:
            return self._rejected(proposal, snapshot, "invalid_diff")
        return (
            ValidationResult(
                status=ValidationStatus.WAITING_APPROVAL,
                proposal_id=proposal.proposal_id,
                workspace_id=snapshot.workspace_id,
                workspace_snapshot_id=snapshot.snapshot_fingerprint,
                target_files=proposal.target_files,
            ),
            prepared,
        )

    def _rejected(
        self,
        proposal: ChangeProposal,
        snapshot: FrozenWorkspaceSnapshot,
        code: str,
    ) -> tuple[ValidationResult, None]:
        return (
            ValidationResult(
                status=ValidationStatus.REJECTED,
                proposal_id=proposal.proposal_id,
                workspace_id=snapshot.workspace_id,
                workspace_snapshot_id=snapshot.snapshot_fingerprint,
                target_files=proposal.target_files,
                error_code=code,
            ),
            None,
        )

    def _changed(
        self, proposal: ChangeProposal, snapshot: FrozenWorkspaceSnapshot
    ) -> tuple[ValidationResult, None]:
        return (
            ValidationResult(
                status=ValidationStatus.WORKSPACE_CHANGED,
                proposal_id=proposal.proposal_id,
                workspace_id=snapshot.workspace_id,
                workspace_snapshot_id=snapshot.snapshot_fingerprint,
                target_files=proposal.target_files,
                error_code="workspace_changed",
            ),
            None,
        )

    def _current_files(
        self,
        proposal: ChangeProposal,
        snapshot_files: dict[str, WorkspaceFileSummary],
    ) -> dict[str, ValidatedWorkspaceFile] | None:
        current: dict[str, ValidatedWorkspaceFile] = {}
        try:
            for relative_path in proposal.target_files:
                file = read_workspace_file(self._root, relative_path)
                summary = _summary(relative_path, file)
                if summary != snapshot_files[relative_path]:
                    return None
                current[relative_path] = file
        except WorkspaceFileInvalid:
            return None
        return current

    def _summary(self, relative_path: str) -> WorkspaceFileSummary:
        return _summary(relative_path, read_workspace_file(self._root, relative_path))

    def _prepare(
        self,
        proposal: ChangeProposal,
        snapshot: FrozenWorkspaceSnapshot,
        current: dict[str, ValidatedWorkspaceFile],
    ) -> PreparedChange:
        sections = _diff_sections(proposal.diff)
        if tuple(section.relative_path for section in sections) != tuple(
            proposal.target_files
        ):
            raise ValueError("diff targets do not match proposal")
        files: list[PreparedFileChange] = []
        for section in sections:
            file = current[section.relative_path]
            source, newline = _normalize_text(file.content)
            patched = _apply_section(source, section)
            after = patched.encode("utf-8").replace(b"\n", newline)
            if not after or len(after) > MAX_WORKSPACE_FILE_SIZE:
                raise _InvalidText("patched text size is invalid")
            files.append(
                PreparedFileChange(
                    relative_path=section.relative_path,
                    before=file.content,
                    after=after,
                    identity=file.identity,
                    parent_identities=file.parent_identities,
                )
            )
        return PreparedChange(proposal=proposal, snapshot=snapshot, files=tuple(files))


@dataclass(frozen=True)
class _DiffSection:
    relative_path: str
    hunks: tuple["_DiffHunk", ...]


@dataclass(frozen=True)
class _DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    entries: tuple[tuple[str, str], ...]


class _InvalidText(ValueError):
    pass


def _diff_sections(diff: str) -> tuple[_DiffSection, ...]:
    lines = _strict_lines(diff)
    sections: list[_DiffSection] = []
    index = 0
    while index < len(lines):
        match = _DIFF_HEADER.fullmatch(lines[index])
        if match is None:
            raise ValueError("diff header is invalid")
        path = match.group(1)
        if (
            match.group(2) != path
            or index + 2 >= len(lines)
            or _normalized_diff_path(path) != path
        ):
            raise ValueError("diff header is invalid")
        old = _OLD_HEADER.fullmatch(lines[index + 1])
        new = _NEW_HEADER.fullmatch(lines[index + 2])
        if old is None or new is None or old.group(1) != path or new.group(1) != path:
            raise ValueError("diff file header is invalid")
        index += 3
        hunks: list[_DiffHunk] = []
        while index < len(lines) and not lines[index].startswith("diff --git "):
            header = _HUNK.fullmatch(lines[index])
            if header is None:
                raise ValueError("diff hunk is invalid")
            old_start = int(header.group(1))
            old_count = int(header.group(2) or "1")
            new_start = int(header.group(3))
            new_count = int(header.group(4) or "1")
            index += 1
            entries: list[tuple[str, str]] = []
            while index < len(lines) and not lines[index].startswith(
                ("@@ ", "diff --git ")
            ):
                line = lines[index]
                if not line or line[0] not in {" ", "+", "-"}:
                    raise ValueError("diff line is invalid")
                entries.append((line[0], line[1:]))
                index += 1
            if not entries:
                raise ValueError("diff hunk is empty")
            old_lines = sum(prefix in {" ", "-"} for prefix, _ in entries)
            new_lines = sum(prefix in {" ", "+"} for prefix, _ in entries)
            if old_lines != old_count or new_lines != new_count:
                raise ValueError("diff hunk count is invalid")
            hunks.append(
                _DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    entries=tuple(entries),
                )
            )
        if not hunks:
            raise ValueError("diff has no hunk")
        sections.append(_DiffSection(relative_path=path, hunks=tuple(hunks)))
    if not sections or len({item.relative_path.casefold() for item in sections}) != len(
        sections
    ):
        raise ValueError("diff sections are invalid")
    return tuple(sections)


def _apply_section(source: str, section: _DiffSection) -> str:
    if not source.endswith("\n"):
        raise ValueError("source must end with newline")
    source_lines = source[:-1].split("\n")
    output: list[str] = []
    cursor = 0
    for hunk in section.hunks:
        start = hunk.old_start - 1 if hunk.old_count else hunk.old_start
        if start < cursor or start > len(source_lines):
            raise ValueError("diff hunk position is invalid")
        output.extend(source_lines[cursor:start])
        new_start = hunk.new_start - 1 if hunk.new_count else hunk.new_start
        if len(output) != new_start:
            raise ValueError("diff new hunk position is invalid")
        cursor = start
        for prefix, value in hunk.entries:
            if prefix == "+":
                output.append(value)
            else:
                if cursor >= len(source_lines) or source_lines[cursor] != value:
                    raise ValueError("diff context does not match source")
                if prefix == " ":
                    output.append(value)
                cursor += 1
    output.extend(source_lines[cursor:])
    if not output:
        return ""
    return "\n".join(output) + "\n"


def _summary(relative_path: str, file: ValidatedWorkspaceFile) -> WorkspaceFileSummary:
    return WorkspaceFileSummary(
        relative_path=relative_path,
        sha256=hashlib.sha256(file.content).hexdigest(),
        size=len(file.content),
        language=_language(relative_path),
    )


def _normalize_text(content: bytes) -> tuple[str, bytes]:
    if b"\r\n" in content:
        without_crlf = content.replace(b"\r\n", b"")
        if b"\r" in without_crlf or b"\n" in without_crlf:
            raise _InvalidText("mixed newline styles are forbidden")
        newline = b"\r\n"
    else:
        if b"\r" in content:
            raise _InvalidText("mixed newline styles are forbidden")
        newline = b"\n"
    if not content or not content.endswith(newline):
        raise _InvalidText("source must end with a newline")
    text = content.decode("utf-8")
    if newline == b"\r\n":
        text = text.replace("\r\n", "\n")
    return text, newline


def _normalized_diff_path(path: str) -> str:
    from embedded_copilot.workspace_runtime.models import safe_relative_path

    return safe_relative_path(path)


def _strict_lines(value: str) -> list[str]:
    if "\r\n" in value:
        without_crlf = value.replace("\r\n", "")
        if "\r" in without_crlf:
            raise ValueError("bare carriage return is forbidden")
        value = value.replace("\r\n", "\n")
    elif "\r" in value:
        raise ValueError("bare carriage return is forbidden")
    lines = value.split("\n")
    if lines and not lines[-1]:
        lines.pop()
    return lines


def _language(path: str) -> WorkspaceLanguage:
    suffix = "." + path.rsplit(".", 1)[1].casefold() if "." in path else ""
    if suffix in {".c", ".h"}:
        return WorkspaceLanguage.C
    if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hxx"}:
        return WorkspaceLanguage.CPP
    if suffix == ".py":
        return WorkspaceLanguage.PYTHON
    if suffix in {".txt", ".md", ".ini", ".cfg", ".conf"}:
        return WorkspaceLanguage.TEXT
    return WorkspaceLanguage.UNKNOWN
