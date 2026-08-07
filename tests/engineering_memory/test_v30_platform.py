from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory import (
    ApprovalAudit,
    ApprovedEngineeringMemory,
    EngineeringMemoryQuery,
    EngineeringMemoryRetrievalService,
    EngineeringMemoryType,
    InMemoryApprovedEngineeringMemoryStore,
)
from embedded_copilot.memory_automation import (
    MemoryApprovalProjection,
    MemoryPromotionService,
    MemorySourceKind,
    MemorySourceProjection,
    MemoryType,
    VersionMemoryInput,
    create_memory_automation,
)
from embedded_copilot.memory_automation.exceptions import MemoryApprovalRejected

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _fact(memory_id: str = "memory-1") -> ApprovedEngineeringMemory:
    return ApprovedEngineeringMemory.create(
        memory_id=memory_id,
        project_id="project-1",
        source_reference="conversation:session-1",
        memory_type=EngineeringMemoryType.DECISION,
        summary="Use ESP32 for the camera node.",
        decision="Choose ESP32.",
        reason="The required camera interface is available.",
        confidence=0.9,
        evidence=("conversation:session-1",),
        approval_audit=ApprovalAudit(
            approval_id="approval-1",
            candidate_fingerprint=FP,
            reviewer="reviewer-1",
            decision="APPROVED",
            approved_at=NOW,
        ),
    )


def test_approved_fact_is_strict_immutable_and_fingerprinted() -> None:
    fact = _fact()
    assert fact.fingerprint.startswith("sha256:")
    assert fact.evidence == ("conversation:session-1",)
    with pytest.raises(ValidationError):
        fact.summary = "changed"
    with pytest.raises(ValidationError):
        ApprovedEngineeringMemory.model_validate(
            {**fact.model_dump(), "unexpected": True}
        )


def test_store_accepts_only_approved_facts_and_returns_copies() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    saved = store.save(_fact())
    assert saved == _fact()
    returned = store.get("project-1", "memory-1")
    assert returned == saved
    assert returned is not saved
    pending_values = saved.model_dump(mode="python")
    pending_values["status"] = "PENDING"
    pending = ApprovedEngineeringMemory.model_construct(**pending_values)
    with pytest.raises(ValidationError):
        store.save(pending)


def test_store_extended_methods_reuse_the_approved_fact_store() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    fact = _fact()

    created = store.create_record(fact)

    assert store.get_record("project-1", "memory-1") == created
    assert store.retrieve_verified("project-1") == (created,)
    assert store.query_records(
        EngineeringMemoryQuery(project_id="project-1", query="camera")
    ) == (created,)
    assert store.fingerprint_check("project-1", "memory-1", created.fingerprint)
    assert not store.fingerprint_check(
        "project-1", "memory-1", "sha256:" + "0" * 64
    )


def test_retrieval_returns_only_approved_project_bound_memories() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    store.save(_fact())
    store.save(_fact("memory-2"))
    result = EngineeringMemoryRetrievalService(store).query(
        EngineeringMemoryQuery(project_id="project-1", query="ESP32 camera")
    )
    assert tuple(item.memory_id for item in result.memories) == (
        "memory-1",
        "memory-2",
    )
    assert all(item.status == "APPROVED" for item in result.memories)


def _candidate(memory_type: MemoryType):
    source = MemorySourceProjection(
        source_type=MemorySourceKind.CONVERSATION_SUMMARY,
        source_id="project-1",
        source_reference="conversation:session-1",
        source_fingerprint=FP,
        observed_at=NOW,
    )
    return create_memory_automation().project(
        VersionMemoryInput(
            source=source,
            summary="Use ESP32 for the camera node.",
            memory_type=memory_type,
        )
    )


def test_promotion_writes_approved_fact_only_after_approval() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    candidate = _candidate(MemoryType.DECISION)
    approval = MemoryApprovalProjection(
        memory_id=candidate.memory_id,
        candidate_fingerprint=candidate.fingerprint,
        reviewer="reviewer-1",
        decision="APPROVED",
        reviewed_at=NOW,
    )
    fact = MemoryPromotionService(approved_store=store).promote(candidate, approval)
    assert fact.status == "APPROVED"
    assert store.list("project-1") == (fact,)


def test_unsupported_evidence_type_fails_closed_without_store_write() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    candidate = _candidate(MemoryType.DEBUG_ANALYSIS_RESULT)
    approval = MemoryApprovalProjection(
        memory_id=candidate.memory_id,
        candidate_fingerprint=candidate.fingerprint,
        reviewer="reviewer-1",
        decision="APPROVED",
        reviewed_at=NOW,
    )
    with pytest.raises(MemoryApprovalRejected):
        MemoryPromotionService(approved_store=store).promote(candidate, approval)
    assert store.list("project-1") == ()
