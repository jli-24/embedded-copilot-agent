from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import (
    MemoryContextEvidence,
    MemoryRankingBreakdown,
    MemoryTrustBasis,
)
from embedded_copilot.engineering_memory.context_builder import (
    RankedMemoryContext,
    build_memory_context,
)
from embedded_copilot.engineering_memory.models import MemorySourceType, MemoryType
from embedded_copilot.engineering_memory.ranking import RankedMemoryItem
from embedded_copilot.knowledge.source import KnowledgeSourceType
from embedded_copilot.supervisor.context import (
    EngineeringPlanningContext,
    PlanningKnowledgeContext,
    PlanningKnowledgeEvidence,
    build_engineering_planning_context,
)
from embedded_copilot.verification_agent import VerificationSubjectType

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
FINGERPRINT_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")


def _ranking(*, usage: int = 0) -> MemoryRankingBreakdown:
    total = (4 * 1000 + 3 * 1000 + 2 * usage + 1000) // 10
    return MemoryRankingBreakdown(
        verification_millis=1000,
        domain_millis=1000,
        usage_millis=usage,
        recency_millis=1000,
        total_millis=total,
        relevance_score=total / 1000,
    )


def _memory_context(
    record_id: str = "record-1",
    *,
    trust_basis: MemoryTrustBasis = MemoryTrustBasis.VERIFICATION,
    usage: int = 0,
) -> RankedMemoryContext:
    ranking = _ranking(usage=usage)
    verified = trust_basis is MemoryTrustBasis.VERIFICATION
    item = RankedMemoryItem(
        record_id=record_id,
        memory_type=MemoryType.COMPONENT,
        logical_key=f"component:{record_id}",
        ranking=ranking,
    )
    evidence = MemoryContextEvidence(
        record_id=record_id,
        memory_type=MemoryType.COMPONENT,
        logical_key=f"component:{record_id}",
        trust_basis=trust_basis,
        verification_subject=(
            VerificationSubjectType.HARDWARE if verified else None
        ),
        verification_confidence=1.0 if verified else None,
        provenance_source_type=(
            MemorySourceType.VERIFICATION_RESULT
            if verified
            else MemorySourceType.MANUAL_DECISION
        ),
        provenance_reference=("verification-1" if verified else "approval-1"),
        last_transition_at=UTC_TIME,
        ranking=ranking,
    )
    return build_memory_context((item,), evidence=(evidence,))


def _source(
    source_id: str = "datasheet-1",
    *,
    trust_level: float = 0.8,
) -> PlanningKnowledgeEvidence:
    return PlanningKnowledgeEvidence(
        source_id=source_id,
        source_type=KnowledgeSourceType.DATASHEET,
        reference=f"https://docs.example.test/{source_id}",
        trust_level=trust_level,
    )


def _knowledge_context(
    *sources: PlanningKnowledgeEvidence,
) -> PlanningKnowledgeContext:
    return PlanningKnowledgeContext(sources=sources or (_source(),))


def _fuse(
    *,
    knowledge: PlanningKnowledgeContext | None = None,
    memory: RankedMemoryContext | None = None,
) -> EngineeringPlanningContext:
    return build_engineering_planning_context(
        knowledge_context=knowledge,
        memory_context=memory,
    )


def test_knowledge_only_fusion_preserves_sources_and_confidence() -> None:
    knowledge = _knowledge_context(
        _source("datasheet-1", trust_level=0.8),
        _source("official-1", trust_level=0.6),
    )
    context = _fuse(knowledge=knowledge)
    assert context.knowledge_context == knowledge
    assert context.memory_context is None
    assert context.confidence == 0.6


def test_memory_only_fusion_preserves_memory_confidence() -> None:
    memory = _memory_context(trust_basis=MemoryTrustBasis.HUMAN_APPROVAL)
    context = _fuse(memory=memory)
    assert context.knowledge_context is None
    assert context.memory_context == memory
    assert context.confidence == 0.5


def test_combined_fusion_uses_minimum_available_confidence() -> None:
    context = _fuse(
        knowledge=_knowledge_context(_source(trust_level=0.7)),
        memory=_memory_context(),
    )
    assert context.confidence == 0.7


def test_knowledge_and_memory_provenance_remain_separate() -> None:
    context = _fuse(
        knowledge=_knowledge_context(),
        memory=_memory_context(),
    )
    assert context.knowledge_context is not None
    assert context.memory_context is not None
    assert context.knowledge_context.sources[0].source_id == "datasheet-1"
    assert context.memory_context.records[0].record_id == "record-1"
    assert "context" not in EngineeringPlanningContext.model_fields


def test_fusion_fingerprint_is_deterministic_and_canonical() -> None:
    knowledge = _knowledge_context()
    memory = _memory_context()
    first = _fuse(knowledge=knowledge, memory=memory)
    second = _fuse(knowledge=knowledge, memory=memory)
    assert FINGERPRINT_PATTERN.fullmatch(first.context_fingerprint)
    assert first == second


def test_object_field_order_does_not_change_fusion_fingerprint() -> None:
    source = _source()
    recreated = PlanningKnowledgeEvidence.model_validate(
        dict(reversed(tuple(source.model_dump(mode="python").items())))
    )
    first = _fuse(knowledge=_knowledge_context(source), memory=_memory_context())
    second = _fuse(knowledge=_knowledge_context(recreated), memory=_memory_context())
    assert first.context_fingerprint == second.context_fingerprint


def test_different_memory_fingerprint_changes_fusion_fingerprint() -> None:
    knowledge = _knowledge_context()
    first = _fuse(knowledge=knowledge, memory=_memory_context())
    second = _fuse(knowledge=knowledge, memory=_memory_context("record-2"))
    assert first.context_fingerprint != second.context_fingerprint


def test_both_unavailable_builds_empty_planning_context() -> None:
    context = _fuse()
    assert context.knowledge_context is None
    assert context.memory_context is None
    assert context.confidence == 0.0
    assert FINGERPRINT_PATTERN.fullmatch(context.context_fingerprint)


def test_empty_knowledge_does_not_reduce_nonempty_memory_confidence() -> None:
    empty_knowledge = PlanningKnowledgeContext(sources=())
    context = _fuse(knowledge=empty_knowledge, memory=_memory_context())
    assert context.confidence == 1.0


def test_empty_memory_does_not_reduce_nonempty_knowledge_confidence() -> None:
    empty_memory = build_memory_context((), evidence=())
    context = _fuse(knowledge=_knowledge_context(), memory=empty_memory)
    assert context.confidence == 0.8


@pytest.mark.parametrize(
    "collection",
    (
        lambda value: [value],
        lambda value: {value},
        lambda value: (item for item in (value,)),
    ),
)
def test_knowledge_sources_collection_must_itself_be_a_tuple(
    collection: Callable[[PlanningKnowledgeEvidence], object],
) -> None:
    with pytest.raises(ValidationError, match="tuple"):
        PlanningKnowledgeContext(  # type: ignore[arg-type]
            sources=collection(_source())
        )


def test_duplicate_knowledge_source_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _knowledge_context(_source(), _source(trust_level=0.5))


@pytest.mark.parametrize("trust_level", (True, 1, float("nan"), float("inf")))
def test_trust_level_must_be_a_strict_finite_float(trust_level: object) -> None:
    with pytest.raises(ValidationError, match="trust"):
        _source(trust_level=trust_level)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "reference",
    (
        "C:\\private\\document.pdf",
        "\\\\server\\private\\document.pdf",
        "file:///private/document.pdf",
        "api_key=private-value",
        "line one\nline two",
        "contains\x00nul",
    ),
)
def test_knowledge_reference_rejects_local_or_sensitive_content(
    reference: str,
) -> None:
    with pytest.raises(ValidationError, match="reference"):
        PlanningKnowledgeEvidence(
            source_id="source-1",
            source_type=KnowledgeSourceType.OFFICIAL_DOC,
            reference=reference,
            trust_level=0.8,
        )


def test_tampered_nested_knowledge_is_rejected_not_downgraded() -> None:
    source = _source()
    object.__setattr__(source, "trust_level", True)
    context = PlanningKnowledgeContext.model_construct(sources=(source,))
    with pytest.raises(ValueError):
        _fuse(knowledge=context)


def test_tampered_memory_fingerprint_is_rejected_not_downgraded() -> None:
    memory = _memory_context()
    object.__setattr__(memory, "context_fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="fingerprint"):
        _fuse(memory=memory)


def test_planning_context_is_strict_frozen_and_forbids_extra() -> None:
    context = _fuse()
    assert EngineeringPlanningContext.model_config == {
        "frozen": True,
        "strict": True,
        "extra": "forbid",
        "hide_input_in_errors": True,
        "revalidate_instances": "always",
    }
    with pytest.raises(ValidationError):
        context.confidence = 1.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringPlanningContext(
            **context.model_dump(),
            unexpected="value",  # type: ignore[call-arg]
        )


def test_invalid_or_stale_fusion_fingerprint_is_rejected() -> None:
    context = _fuse(knowledge=_knowledge_context(), memory=_memory_context())
    values = context.model_dump(exclude={"context_fingerprint"})
    with pytest.raises(ValidationError):
        EngineeringPlanningContext(
            **values,
            context_fingerprint="sha256:" + "A" * 64,
        )
    with pytest.raises(ValidationError, match="fingerprint"):
        EngineeringPlanningContext(
            **values,
            context_fingerprint="sha256:" + "0" * 64,
        )


def test_context_contains_no_payload_or_runtime_metadata() -> None:
    context = _fuse(knowledge=_knowledge_context(), memory=_memory_context())
    serialized = context.model_dump(mode="python")
    forbidden = {
        "payload",
        "summary",
        "response_body",
        "runtime_object",
        "request_id",
        "trace_id",
        "timestamp",
        "audit",
    }
    assert forbidden.isdisjoint(serialized)
    assert context.knowledge_context is not None
    assert forbidden.isdisjoint(
        context.knowledge_context.sources[0].model_dump(mode="python")
    )


def test_fusion_does_not_mutate_inputs_and_returns_deep_copies() -> None:
    knowledge = _knowledge_context()
    memory = _memory_context()
    knowledge_before = knowledge.model_dump_json()
    memory_before = memory.model_dump_json()

    context = _fuse(knowledge=knowledge, memory=memory)

    assert knowledge.model_dump_json() == knowledge_before
    assert memory.model_dump_json() == memory_before
    assert context.knowledge_context == knowledge
    assert context.memory_context == memory
    assert context.knowledge_context is not knowledge
    assert context.memory_context is not memory
