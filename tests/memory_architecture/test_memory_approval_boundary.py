from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_memory import (
    AffectedMemoryRecord,
    EngineeringDecisionMemory,
    EngineeringMemorySnapshot,
    MemoryMutationOutcome,
    MemoryMutationResult,
    MemoryProvenance,
    MemorySnapshotRecord,
    MemorySnapshotType,
    MemoryStatus,
    MemorySourceType,
)
from embedded_copilot.memory_automation import (
    MemoryApprovalProjection,
    MemorySourceKind,
    MemorySourceProjection,
    MemoryType,
    MemoryPromotionService,
    VersionMemoryInput,
    create_memory_automation,
)
from embedded_copilot.memory_automation.exceptions import MemoryApprovalRejected


NOW = datetime(2026, 8, 1, tzinfo=UTC)


class _EngineeringMemoryFake:
    def __init__(self) -> None:
        self.calls = []
        self.record_id = None

    def execute(self, request):
        self.calls.append(request)
        if request.command_type.value == "GET_VERIFIED_SNAPSHOT":
            payload = EngineeringDecisionMemory(
                decision_topic="decision-topic",
                decision="Keep the boundary explicit.",
                rationale_summary="The boundary remains auditable.",
            )
            provenance = MemoryProvenance(
                source_type=MemorySourceType.USER_INPUT,
                source_reference="conversation:session-1",
                source_revision="sha256:" + "a" * 64,
                created_by="memory-promotion",
                observed_at=NOW,
            )
            record = MemorySnapshotRecord(
                record_id=self.record_id,
                memory_type=payload.memory_type,
                logical_key="decision:decision-topic",
                payload=payload,
                provenance=provenance,
                status=MemoryStatus.VERIFIED,
                record_revision=1,
            )
            return EngineeringMemorySnapshot(
                request_id=request.request_id,
                snapshot_type=MemorySnapshotType.VERIFIED,
                project_id=request.project_id,
                memory_id=request.memory_id,
                aggregate_revision=2,
                engineering_decisions=(record,),
                snapshot_fingerprint="sha256:" + "b" * 64,
            )
        result = MemoryMutationResult(
            request_id=request.request_id,
            operation_id=request.operation_id,
            command_type=request.command_type,
            outcome=(
                MemoryMutationOutcome.CREATED
                if request.command_type.value == "CREATE_CANDIDATE"
                else MemoryMutationOutcome.TRANSITIONED
            ),
            affected_records=(
                AffectedMemoryRecord(
                    record_id=request.record_id,
                    status=(
                        MemoryStatus.CANDIDATE
                        if request.command_type.value == "CREATE_CANDIDATE"
                        else MemoryStatus.VERIFIED
                    ),
                    record_revision=0,
                ),
            ),
            aggregate_revision=(
                1 if request.command_type.value == "CREATE_CANDIDATE" else 2
            ),
        )
        if request.command_type.value == "CREATE_CANDIDATE":
            self.record_id = request.record_id
        return result


def _candidate(memory_type: MemoryType):
    source = MemorySourceProjection(
        source_type=MemorySourceKind.CONVERSATION_SUMMARY,
        source_id="project-1",
        source_reference="conversation:session-1",
        source_fingerprint="sha256:" + "a" * 64,
        observed_at=NOW,
    )
    return create_memory_automation().project(
        VersionMemoryInput(
            source=source,
            summary="Keep the boundary explicit.",
            memory_type=memory_type,
        )
    )


def _approval(candidate, *, fingerprint: str | None = None):
    return MemoryApprovalProjection(
        memory_id=candidate.memory_id,
        candidate_fingerprint=fingerprint or candidate.fingerprint,
        reviewer="reviewer-1",
        decision="APPROVED",
        reviewed_at=NOW,
    )


def test_pending_or_mismatched_candidate_never_reaches_engineering_memory() -> None:
    fake = _EngineeringMemoryFake()
    with pytest.raises(MemoryApprovalRejected):
        MemoryPromotionService(fake).promote(
            _candidate(MemoryType.DECISION),
            _approval(_candidate(MemoryType.DECISION), fingerprint="sha256:" + "c" * 64),
        )
    assert fake.calls == []


def test_unsupported_conversation_type_is_rejected_without_store_write() -> None:
    fake = _EngineeringMemoryFake()
    candidate = _candidate(MemoryType.DEBUG_ANALYSIS_RESULT)
    with pytest.raises(MemoryApprovalRejected):
        MemoryPromotionService(fake).promote(candidate, _approval(candidate))
    assert fake.calls == []


def test_approved_decision_promotes_through_engineering_memory_port() -> None:
    fake = _EngineeringMemoryFake()
    candidate = _candidate(MemoryType.DECISION)
    projection = MemoryPromotionService(fake).promote(candidate, _approval(candidate))
    assert projection.status == "APPROVED"
    assert [item.command_type.value for item in fake.calls] == [
        "CREATE_CANDIDATE",
        "APPLY_HUMAN_APPROVAL",
        "GET_VERIFIED_SNAPSHOT",
    ]
