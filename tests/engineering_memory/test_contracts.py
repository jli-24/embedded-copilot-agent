from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from embedded_copilot.engineering_memory.models import (
    AffectedMemoryRecord,
    ApplyHumanApprovalRequest,
    ApplyVerificationRequest,
    BoardProfileMemory,
    CreateCandidateRequest,
    CreateReplacementCandidateRequest,
    EngineeringMemoryHistoryPage,
    EngineeringMemoryRequest,
    EngineeringMemoryResult,
    EngineeringMemorySnapshot,
    EngineeringMemoryRecord,
    GetCandidateSnapshotRequest,
    GetHistoryRequest,
    GetVerifiedSnapshotRequest,
    HumanApprovalEvidence,
    MemoryAction,
    MemoryAuditEvent,
    MemoryAuditEventType,
    MemoryAuthorizationRequest,
    MemoryCommandType,
    MemoryMutationOutcome,
    MemoryMutationResult,
    MemoryPermissionDecision,
    MemoryProvenance,
    MemorySourceType,
    MemoryPermissionStatus,
    MemoryStatus,
    MemoryType,
    RevokeRecordRequest,
    VerificationEvidenceBinding,
    _MemoryRequestContract,
    _MemoryWriteRequestContract,
)
from embedded_copilot.engineering_memory.fingerprint import canonical_fingerprint
from embedded_copilot.engineering_memory.rules import (
    build_candidate_record,
    memory_context_id,
)
from embedded_copilot.verification_agent import (
    VerificationStatus,
    VerificationSubjectType,
)

UTC_TIME = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


class _ReadProbe(_MemoryRequestContract):
    pass


class _WriteProbe(_MemoryWriteRequestContract):
    pass


def _common(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "request_id": "req-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "caller": "caller-1",
        "requested_at": UTC_TIME,
    }
    values.update(changes)
    return values


def test_contract_is_frozen_strict_and_rejects_extra_fields() -> None:
    request = _ReadProbe(**_common())
    with pytest.raises(ValidationError):
        request.request_id = "changed"
    with pytest.raises(ValidationError):
        _ReadProbe(**request.model_dump(), unexpected=True)
    with pytest.raises(ValidationError):
        _WriteProbe(**_common(), operation_id="operation-1", expected_revision=True)
    assert tuple(request.model_dump()) == (
        "request_id",
        "project_id",
        "memory_id",
        "caller",
        "requested_at",
    )


def test_datetime_must_be_aware_and_is_normalized_to_utc() -> None:
    with pytest.raises(ValidationError, match="timezone aware"):
        _ReadProbe(**_common(requested_at=datetime(2026, 7, 29, 12, 0)))
    plus_eight = datetime(2026, 7, 29, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    value = _ReadProbe(**_common(requested_at=plus_eight))
    assert value.requested_at == UTC_TIME
    assert value.requested_at.utcoffset() == timedelta(0)


def test_identifiers_and_write_fields_are_strict() -> None:
    with pytest.raises(ValidationError):
        _ReadProbe(**_common(request_id=""))
    with pytest.raises(ValidationError):
        _ReadProbe(**_common(project_id="../outside"))
    with pytest.raises(ValidationError):
        _WriteProbe(**_common(), operation_id="", expected_revision=0)
    with pytest.raises(ValidationError):
        _WriteProbe(**_common(), operation_id="operation-1", expected_revision=-1)
    with pytest.raises(ValidationError):
        _ReadProbe(**_common(project_id="project:ambiguous"))


def test_contract_enums_are_closed() -> None:
    assert tuple(MemoryStatus) == (
        MemoryStatus.CANDIDATE,
        MemoryStatus.VERIFIED,
        MemoryStatus.REJECTED,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.REVOKED,
    )
    assert len(tuple(MemoryType)) == 8
    assert len(tuple(MemoryCommandType)) == 8
    assert len(tuple(MemoryAction)) == 8
    assert tuple(MemoryPermissionStatus) == (
        MemoryPermissionStatus.ALLOWED,
        MemoryPermissionStatus.DENIED,
    )
    assert tuple(MemoryAuditEventType) == (
        MemoryAuditEventType.MEMORY_REQUESTED,
        MemoryAuditEventType.MEMORY_COMPLETED,
        MemoryAuditEventType.MEMORY_REJECTED,
        MemoryAuditEventType.MEMORY_FAILED,
    )
    assert tuple(MemoryMutationOutcome) == (
        MemoryMutationOutcome.CREATED,
        MemoryMutationOutcome.TRANSITIONED,
        MemoryMutationOutcome.REVOKED,
    )


def _board_payload() -> BoardProfileMemory:
    return BoardProfileMemory(
        board_id="board-1",
        board_name="Sensor Board",
        mcu_family="STM32",
        mcu_model="STM32F407VG",
        architecture="ARM Cortex-M4",
    )


def _provenance() -> MemoryProvenance:
    return MemoryProvenance(
        source_type=MemorySourceType.USER_INPUT,
        source_reference="source-1",
        source_revision="revision-1",
        created_by="caller-1",
        observed_at=UTC_TIME,
    )


def test_new_record_has_candidate_revision_zero_and_initial_history() -> None:
    record = build_candidate_record(
        request_id="req-1",
        operation_id="operation-1",
        project_id="project-1",
        memory_id="memory-1",
        record_id="record-1",
        payload=_board_payload(),
        provenance=_provenance(),
        requested_at=UTC_TIME,
        aggregate_revision=1,
    )
    assert isinstance(record, EngineeringMemoryRecord)
    assert record.status is MemoryStatus.CANDIDATE
    assert record.record_revision == 0
    assert record.logical_key == "board-profile"
    assert record.created_aggregate_revision == 1
    assert record.last_updated_aggregate_revision == 1
    assert tuple(
        (item.from_status, item.to_status) for item in record.state_history
    ) == ((None, MemoryStatus.CANDIDATE),)
    with pytest.raises(ValidationError):
        record.state_history = ()


def test_memory_context_id_binds_record_revision() -> None:
    assert (
        memory_context_id("project-1", "memory-1", "record-1", 3)
        == "memory:project-1:memory-1:record-1:3"
    )
    with pytest.raises(ValueError):
        memory_context_id("../project", "memory-1", "record-1", 0)


def test_evidence_contracts_are_frozen_bound_and_content_limited() -> None:
    verification = VerificationEvidenceBinding(
        verification_request_id="verify-1",
        subject_type=VerificationSubjectType.HARDWARE,
        result_status=VerificationStatus.REVIEW_REQUIRED,
        request_fingerprint="sha256:" + "a" * 64,
        result_fingerprint="sha256:" + "b" * 64,
        requested_at=UTC_TIME,
        summary_reference="summary-1",
    )
    approval = HumanApprovalEvidence(
        approval_id="approval-1",
        record_id="record-1",
        record_revision=0,
        approved_by="reviewer-1",
        reason_code="PROJECT_ACCEPTED",
        approved_at=UTC_TIME,
    )
    assert verification.requested_at == approval.approved_at == UTC_TIME
    with pytest.raises(ValidationError):
        VerificationEvidenceBinding(
            **verification.model_dump() | {"summary_reference": "C:/private/log.txt"}
        )
    with pytest.raises(ValidationError):
        HumanApprovalEvidence(**approval.model_dump() | {"record_revision": True})


def _create_request(**changes: object) -> CreateCandidateRequest:
    values: dict[str, object] = {
        **_common(),
        "command_type": MemoryCommandType.CREATE_CANDIDATE,
        "operation_id": "operation-1",
        "expected_revision": 0,
        "record_id": "record-1",
        "payload": _board_payload(),
        "provenance": _provenance(),
    }
    values.update(changes)
    return CreateCandidateRequest(**values)


def test_command_union_is_closed_and_write_fields_are_bound() -> None:
    request = _create_request()
    validated = TypeAdapter(EngineeringMemoryRequest).validate_python(request)
    assert validated == request
    with pytest.raises(ValidationError):
        _create_request(command_type=MemoryCommandType.GET_HISTORY)
    with pytest.raises(ValidationError):
        CreateCandidateRequest(
            **request.model_dump() | {"payload": request.payload.model_dump()}
        )
    assert set(TypeAdapter(EngineeringMemoryRequest).core_schema)


def test_all_eight_commands_have_fixed_shapes() -> None:
    assert tuple(item.value for item in MemoryCommandType) == (
        "CREATE_CANDIDATE",
        "CREATE_REPLACEMENT_CANDIDATE",
        "APPLY_VERIFICATION",
        "APPLY_HUMAN_APPROVAL",
        "REVOKE_RECORD",
        "GET_VERIFIED_SNAPSHOT",
        "GET_CANDIDATE_SNAPSHOT",
        "GET_HISTORY",
    )
    assert CreateReplacementCandidateRequest.model_fields["supersedes_record_id"]
    assert ApplyVerificationRequest.model_fields["verification_result"]
    assert ApplyHumanApprovalRequest.model_fields["approval"]
    assert RevokeRecordRequest.model_fields["reason_code"]
    assert "operation_id" not in GetVerifiedSnapshotRequest.model_fields
    assert "operation_id" not in GetCandidateSnapshotRequest.model_fields
    assert "operation_id" not in GetHistoryRequest.model_fields


def test_history_cursor_limit_and_canonical_fingerprint_are_deterministic() -> None:
    request = _create_request()
    data = request.model_dump(mode="python")
    data["payload"] = request.payload
    data["provenance"] = request.provenance
    recreated = CreateCandidateRequest.model_validate(
        dict(reversed(tuple(data.items())))
    )
    assert canonical_fingerprint(request) == canonical_fingerprint(recreated)
    assert canonical_fingerprint(request).startswith("sha256:")
    with pytest.raises(ValidationError):
        GetHistoryRequest(**_common(), cursor="offset:1")
    with pytest.raises(ValidationError):
        GetHistoryRequest(**_common(), limit=0)
    with pytest.raises(ValidationError):
        GetHistoryRequest(**_common(), limit=True)


def test_authorization_audit_and_results_are_content_bounded() -> None:
    assert tuple(MemoryAuthorizationRequest.model_fields) == (
        "request_id",
        "operation_id",
        "project_id",
        "memory_id",
        "caller",
        "command_type",
        "action",
        "request_fingerprint",
        "requested_at",
    )
    assert tuple(MemoryPermissionDecision.model_fields) == (
        *tuple(MemoryAuthorizationRequest.model_fields),
        "decision",
        "reason_code",
    )
    assert "payload" not in MemoryAuditEvent.model_fields
    assert "payload" not in MemoryMutationResult.model_fields
    assert AffectedMemoryRecord.model_fields["record_revision"]
    assert TypeAdapter(EngineeringMemoryResult)
    assert EngineeringMemorySnapshot.model_fields["snapshot_fingerprint"]
    assert EngineeringMemoryHistoryPage.model_fields["next_cursor"]
