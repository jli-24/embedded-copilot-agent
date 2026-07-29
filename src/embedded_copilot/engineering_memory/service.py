from __future__ import annotations

import copy

from pydantic import TypeAdapter, ValidationError

from .audit import build_audit_event, record_audit
from .exceptions import (
    EngineeringMemoryRequestRejected,
    MemoryOperationConflict,
    MemoryPermissionDenied,
    MemoryRecordNotFound,
    MemoryRevisionConflict,
    MemoryStateTransitionRejected,
    MemoryStoreUnavailable,
)
from .fingerprint import canonical_fingerprint
from .models import (
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRequest,
    EngineeringMemoryResult,
    EngineeringMemorySnapshot,
    MemoryAction,
    MemoryAuditEventType,
    MemoryAuthorizationRequest,
    MemoryCommandType,
    MemoryMutationResult,
    MemoryPermissionDecision,
    MemoryPermissionStatus,
    MemorySnapshotType,
)
from .ports import EngineeringMemoryStorePort, MemoryAuditSink, MemoryPermissionPort


class _PermissionAdapterFailure(RuntimeError):
    pass


def _action(command_type: MemoryCommandType) -> MemoryAction:
    return {
        MemoryCommandType.GET_VERIFIED_SNAPSHOT: MemoryAction.READ_VERIFIED_MEMORY,
        MemoryCommandType.GET_CANDIDATE_SNAPSHOT: MemoryAction.READ_CANDIDATE_MEMORY,
        MemoryCommandType.GET_HISTORY: MemoryAction.READ_MEMORY_HISTORY,
        MemoryCommandType.CREATE_CANDIDATE: MemoryAction.CREATE_MEMORY_CANDIDATE,
        MemoryCommandType.APPLY_VERIFICATION: MemoryAction.APPLY_VERIFICATION_EVIDENCE,
        MemoryCommandType.APPLY_HUMAN_APPROVAL: MemoryAction.APPLY_HUMAN_APPROVAL,
        MemoryCommandType.CREATE_REPLACEMENT_CANDIDATE: (
            MemoryAction.CREATE_REPLACEMENT_CANDIDATE
        ),
        MemoryCommandType.REVOKE_RECORD: MemoryAction.REVOKE_MEMORY_RECORD,
    }[command_type]


def _authorization(request, request_fingerprint: str) -> MemoryAuthorizationRequest:
    return MemoryAuthorizationRequest(
        request_id=request.request_id,
        operation_id=getattr(request, "operation_id", None),
        project_id=request.project_id,
        memory_id=request.memory_id,
        caller=request.caller,
        command_type=request.command_type,
        action=_action(request.command_type),
        request_fingerprint=request_fingerprint,
        requested_at=request.requested_at,
    )


def _authorized(permission_port, authorization: MemoryAuthorizationRequest) -> None:
    try:
        raw = permission_port.authorize(authorization)
        if not isinstance(raw, MemoryPermissionDecision):
            raise ValueError("permission decision type is invalid")  # noqa: TRY004
        decision = MemoryPermissionDecision.model_validate(copy.deepcopy(raw))
        for field in MemoryAuthorizationRequest.model_fields:
            if getattr(decision, field) != getattr(authorization, field):
                raise ValueError("permission decision binding is invalid")
    except Exception as error:
        raise _PermissionAdapterFailure from error
    if decision.decision is not MemoryPermissionStatus.ALLOWED:
        raise MemoryPermissionDenied()


def _dispatch(store, request, request_fingerprint: str):
    method = {
        MemoryCommandType.CREATE_CANDIDATE: store.create_candidate,
        MemoryCommandType.CREATE_REPLACEMENT_CANDIDATE: (
            store.create_replacement_candidate
        ),
        MemoryCommandType.APPLY_VERIFICATION: store.apply_verification,
        MemoryCommandType.APPLY_HUMAN_APPROVAL: store.apply_human_approval,
        MemoryCommandType.REVOKE_RECORD: store.revoke_record,
        MemoryCommandType.GET_VERIFIED_SNAPSHOT: store.get_verified_snapshot,
        MemoryCommandType.GET_CANDIDATE_SNAPSHOT: store.get_candidate_snapshot,
        MemoryCommandType.GET_HISTORY: store.get_history,
    }[request.command_type]
    if hasattr(request, "operation_id"):
        return method(request, request_fingerprint=request_fingerprint)
    return method(request)


def _validate_result_binding(request, result) -> None:
    if result.request_id != request.request_id:
        raise ValueError("store result request binding is invalid")
    if isinstance(result, MemoryMutationResult):
        if (
            result.operation_id != request.operation_id
            or result.command_type is not request.command_type
        ):
            raise ValueError("store mutation result binding is invalid")
        return
    if result.project_id != request.project_id or result.memory_id != request.memory_id:
        raise ValueError("store query result binding is invalid")
    if request.command_type is MemoryCommandType.GET_HISTORY:
        if not isinstance(result, EngineeringMemoryHistoryPage):
            raise ValueError("store history result type is invalid")
        return
    if not isinstance(result, EngineeringMemorySnapshot):
        raise ValueError("store snapshot result type is invalid")  # noqa: TRY004
    if isinstance(result, EngineeringMemorySnapshot):
        expected = (
            MemorySnapshotType.VERIFIED
            if request.command_type is MemoryCommandType.GET_VERIFIED_SNAPSHOT
            else MemorySnapshotType.CANDIDATE
        )
        if result.snapshot_type is not expected:
            raise ValueError("store snapshot type binding is invalid")


class _EngineeringMemoryPort:
    __slots__ = ("_audit_sink", "_permission_port", "_store")

    def __init__(
        self,
        *,
        store: EngineeringMemoryStorePort,
        permission_port: MemoryPermissionPort,
        audit_sink: MemoryAuditSink,
    ) -> None:
        self._store = store
        self._permission_port = permission_port
        self._audit_sink = audit_sink

    def execute(self, request: EngineeringMemoryRequest) -> EngineeringMemoryResult:
        try:
            checked = TypeAdapter(EngineeringMemoryRequest).validate_python(
                copy.deepcopy(request)
            )
        except ValidationError:
            raise EngineeringMemoryRequestRejected() from None
        request_fingerprint = canonical_fingerprint(checked)
        record_audit(
            self._audit_sink,
            build_audit_event(checked, MemoryAuditEventType.MEMORY_REQUESTED),
        )
        authorization = _authorization(checked, request_fingerprint)
        try:
            _authorized(self._permission_port, authorization)
        except MemoryPermissionDenied:
            record_audit(
                self._audit_sink,
                build_audit_event(checked, MemoryAuditEventType.MEMORY_REJECTED),
            )
            raise
        except _PermissionAdapterFailure as error:
            record_audit(
                self._audit_sink,
                build_audit_event(checked, MemoryAuditEventType.MEMORY_FAILED),
            )
            raise MemoryPermissionDenied() from error
        try:
            raw_result = _dispatch(self._store, checked, request_fingerprint)
            result = TypeAdapter(EngineeringMemoryResult).validate_python(
                copy.deepcopy(raw_result)
            )
            _validate_result_binding(checked, result)
        except (
            EngineeringMemoryRequestRejected,
            MemoryOperationConflict,
            MemoryRecordNotFound,
            MemoryRevisionConflict,
            MemoryStateTransitionRejected,
        ) as error:
            record_audit(
                self._audit_sink,
                build_audit_event(checked, MemoryAuditEventType.MEMORY_REJECTED),
            )
            raise type(error)() from error
        except Exception as error:
            record_audit(
                self._audit_sink,
                build_audit_event(checked, MemoryAuditEventType.MEMORY_FAILED),
            )
            raise MemoryStoreUnavailable() from error
        record_audit(
            self._audit_sink,
            build_audit_event(checked, MemoryAuditEventType.MEMORY_COMPLETED),
        )
        return result
