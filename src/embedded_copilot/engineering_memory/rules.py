from __future__ import annotations

from datetime import datetime

from embedded_copilot.engineering_memory.models import (
    BoardProfileMemory,
    ComponentMemory,
    EngineeringDecisionMemory,
    EngineeringMemoryRecord,
    InterfaceBindingMemory,
    KnownIssueMemory,
    MemoryPayload,
    MemoryProvenance,
    MemoryStateTransition,
    MemoryStatus,
    PinBindingMemory,
    PowerConstraintMemory,
    VerificationHistoryMemory,
    VerificationSubjectType,
    _identifier,
)


def logical_key_for(payload: MemoryPayload) -> str:
    if isinstance(payload, BoardProfileMemory):
        return "board-profile"
    if isinstance(payload, ComponentMemory):
        return f"component:{payload.component_reference}"
    if isinstance(payload, PinBindingMemory):
        return f"pin:{payload.target_id}:{payload.pin_id}"
    if isinstance(payload, InterfaceBindingMemory):
        return f"interface:{payload.target_id}:{payload.interface_id}:{payload.signal}"
    if isinstance(payload, PowerConstraintMemory):
        return f"power:{payload.supply_id}:{payload.load_id}"
    if isinstance(payload, EngineeringDecisionMemory):
        return f"decision:{payload.decision_topic}"
    if isinstance(payload, KnownIssueMemory):
        return f"issue:{payload.issue_key}"
    if isinstance(payload, VerificationHistoryMemory):
        return f"verification:{payload.verification_request_id}"
    raise TypeError("memory payload is invalid")


def memory_context_id(
    project_id: str,
    memory_id: str,
    record_id: str,
    record_revision: int,
) -> str:
    project = _identifier(project_id, field="project_id")
    memory = _identifier(memory_id, field="memory_id")
    record = _identifier(record_id, field="record_id")
    if (
        isinstance(record_revision, bool)
        or not isinstance(record_revision, int)
        or record_revision < 0
    ):
        raise ValueError("record_revision is invalid")
    return f"memory:{project}:{memory}:{record}:{record_revision}"


def build_candidate_record(
    *,
    request_id: str,
    operation_id: str,
    project_id: str,
    memory_id: str,
    record_id: str,
    payload: MemoryPayload,
    provenance: MemoryProvenance,
    requested_at: datetime,
    aggregate_revision: int,
    supersedes_record_id: str | None = None,
) -> EngineeringMemoryRecord:
    transition = MemoryStateTransition(
        from_status=None,
        to_status=MemoryStatus.CANDIDATE,
        request_id=request_id,
        operation_id=operation_id,
        evidence_type="CREATED",
        evidence_reference=provenance.source_reference,
        reason_code="CANDIDATE_CREATED",
        transitioned_at=requested_at,
    )
    return EngineeringMemoryRecord(
        project_id=project_id,
        memory_id=memory_id,
        record_id=record_id,
        memory_type=payload.memory_type,
        logical_key=logical_key_for(payload),
        payload=payload,
        provenance=provenance,
        status=MemoryStatus.CANDIDATE,
        record_revision=0,
        created_aggregate_revision=aggregate_revision,
        last_updated_aggregate_revision=aggregate_revision,
        created_at=requested_at,
        last_transition_at=requested_at,
        verification_bindings=(),
        approval_binding=None,
        state_history=(transition,),
        supersedes_record_id=supersedes_record_id,
        superseded_by_record_id=None,
    )


def verification_subject_is_compatible(
    record: EngineeringMemoryRecord, subject_type: object
) -> bool:
    if isinstance(
        record.payload,
        (
            BoardProfileMemory,
            ComponentMemory,
            PinBindingMemory,
            InterfaceBindingMemory,
            PowerConstraintMemory,
        ),
    ):
        return subject_type is VerificationSubjectType.HARDWARE
    if isinstance(record.payload, (EngineeringDecisionMemory, KnownIssueMemory)):
        return subject_type in tuple(VerificationSubjectType)
    if isinstance(record.payload, VerificationHistoryMemory):
        return subject_type is record.payload.subject_type
    return False
