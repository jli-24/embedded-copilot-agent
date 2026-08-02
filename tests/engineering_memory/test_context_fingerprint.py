from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

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
from embedded_copilot.verification_agent import VerificationSubjectType

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
FINGERPRINT_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")


def _ranking(
    *,
    verification: int = 1000,
    domain: int = 1000,
    usage: int = 0,
    recency: int = 1000,
) -> MemoryRankingBreakdown:
    total = (4 * verification + 3 * domain + 2 * usage + recency) // 10
    return MemoryRankingBreakdown(
        verification_millis=verification,
        domain_millis=domain,
        usage_millis=usage,
        recency_millis=recency,
        total_millis=total,
        relevance_score=total / 1000,
    )


def _item(
    record_id: str = "record-1",
    *,
    memory_type: MemoryType = MemoryType.COMPONENT,
    logical_key: str = "component:U1",
    ranking: MemoryRankingBreakdown | None = None,
) -> RankedMemoryItem:
    return RankedMemoryItem(
        record_id=record_id,
        memory_type=memory_type,
        logical_key=logical_key,
        ranking=_ranking() if ranking is None else ranking,
    )


def _evidence(
    record_id: str = "record-1",
    *,
    memory_type: MemoryType = MemoryType.COMPONENT,
    logical_key: str = "component:U1",
    ranking: MemoryRankingBreakdown | None = None,
    trust_basis: MemoryTrustBasis = MemoryTrustBasis.VERIFICATION,
    last_transition_at: datetime = UTC_TIME,
) -> MemoryContextEvidence:
    verified = trust_basis is MemoryTrustBasis.VERIFICATION
    return MemoryContextEvidence(
        record_id=record_id,
        memory_type=memory_type,
        logical_key=logical_key,
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
        last_transition_at=last_transition_at,
        ranking=_ranking() if ranking is None else ranking,
    )


def _build(
    *,
    items: tuple[RankedMemoryItem, ...] | None = None,
    evidence: tuple[MemoryContextEvidence, ...] | None = None,
) -> RankedMemoryContext:
    return build_memory_context(
        (_item(),) if items is None else items,
        evidence=(_evidence(),) if evidence is None else evidence,
    )


def test_context_contract_is_strict_frozen_and_fingerprint_verified() -> None:
    context = _build()
    assert tuple(RankedMemoryContext.model_fields) == (
        "records",
        "evidence",
        "confidence",
        "context_fingerprint",
    )
    assert RankedMemoryContext.model_config == {
        "frozen": True,
        "strict": True,
        "extra": "forbid",
        "hide_input_in_errors": True,
        "revalidate_instances": "always",
    }
    assert FINGERPRINT_PATTERN.fullmatch(context.context_fingerprint)
    with pytest.raises(ValidationError):
        context.confidence = 0.5  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RankedMemoryContext(
            **context.model_dump(),
            unexpected="value",  # type: ignore[call-arg]
        )


def test_same_input_builds_the_same_fingerprint() -> None:
    first = _build()
    second = _build()
    assert first == second
    assert first.context_fingerprint == second.context_fingerprint


def test_object_field_insertion_order_does_not_change_fingerprint() -> None:
    item = _item()
    evidence = _evidence()
    recreated_item = RankedMemoryItem.model_validate(
        dict(reversed(tuple(item.model_dump(mode="python").items())))
    )
    recreated_evidence = MemoryContextEvidence.model_validate(
        dict(reversed(tuple(evidence.model_dump(mode="python").items())))
    )
    assert _build().context_fingerprint == _build(
        items=(recreated_item,),
        evidence=(recreated_evidence,),
    ).context_fingerprint


def test_record_identity_changes_the_fingerprint() -> None:
    changed = _build(
        items=(_item("record-2"),),
        evidence=(_evidence("record-2"),),
    )
    assert _build().context_fingerprint != changed.context_fingerprint


def test_ranking_breakdown_changes_the_fingerprint() -> None:
    changed_ranking = _ranking(usage=500)
    changed = _build(
        items=(_item(ranking=changed_ranking),),
        evidence=(_evidence(ranking=changed_ranking),),
    )
    assert _build().context_fingerprint != changed.context_fingerprint


def test_context_has_no_raw_memory_or_runtime_content_fields() -> None:
    serialized = _build().model_dump(mode="python")
    forbidden = {
        "payload",
        "finding",
        "approval_body",
        "raw_verification_result",
        "request_id",
        "trace_id",
        "usage_count",
        "audit",
    }
    assert forbidden.isdisjoint(serialized)
    assert forbidden.isdisjoint(serialized["records"][0])
    assert forbidden.isdisjoint(serialized["evidence"][0])


@pytest.mark.parametrize(
    "collection",
    (
        lambda value: [value],
        lambda value: {value},
        lambda value: (item for item in (value,)),
    ),
)
def test_ranked_items_collection_must_itself_be_a_tuple(
    collection: Callable[[RankedMemoryItem], object],
) -> None:
    with pytest.raises(ValueError, match="tuple"):
        build_memory_context(  # type: ignore[arg-type]
            collection(_item()),
            evidence=(_evidence(),),
        )


@pytest.mark.parametrize(
    "collection",
    (
        lambda value: [value],
        lambda value: {value},
        lambda value: (item for item in (value,)),
    ),
)
def test_evidence_collection_must_itself_be_a_tuple(
    collection: Callable[[MemoryContextEvidence], object],
) -> None:
    with pytest.raises(ValueError, match="tuple"):
        build_memory_context(
            (_item(),),
            evidence=collection(_evidence()),  # type: ignore[arg-type]
        )


def test_tampered_nested_ranking_is_rejected() -> None:
    item = _item()
    object.__setattr__(item.ranking, "total_millis", True)
    with pytest.raises(ValueError):
        build_memory_context((item,), evidence=(_evidence(),))


def test_tampered_or_naive_transition_time_is_rejected() -> None:
    evidence = _evidence()
    object.__setattr__(evidence, "last_transition_at", datetime(2026, 7, 30, 3, 0))
    with pytest.raises(ValueError, match="timezone aware"):
        build_memory_context((_item(),), evidence=(evidence,))


def test_transition_time_is_normalized_to_utc() -> None:
    plus_eight = timezone(timedelta(hours=8))
    evidence = _evidence(
        last_transition_at=datetime(2026, 7, 30, 11, 0, tzinfo=plus_eight)
    )
    context = _build(evidence=(evidence,))
    assert context.evidence[0].last_transition_at == UTC_TIME
    assert context.evidence[0].last_transition_at.tzinfo is UTC


def test_empty_context_confidence_is_zero() -> None:
    context = _build(items=(), evidence=())
    assert context.records == ()
    assert context.evidence == ()
    assert context.confidence == 0.0


def test_verification_confidence_uses_evidence_confidence() -> None:
    assert _build().confidence == 1.0


def test_human_approval_confidence_is_one_half() -> None:
    assert _build(
        evidence=(_evidence(trust_basis=MemoryTrustBasis.HUMAN_APPROVAL),)
    ).confidence == 0.5


def test_multiple_evidence_confidence_uses_the_minimum() -> None:
    second_ranking = _ranking(domain=500)
    items = (
        _item(),
        _item(
            "record-2",
            memory_type=MemoryType.KNOWN_ISSUE,
            logical_key="issue:2",
            ranking=second_ranking,
        ),
    )
    evidence = (
        _evidence(),
        _evidence(
            "record-2",
            memory_type=MemoryType.KNOWN_ISSUE,
            logical_key="issue:2",
            ranking=second_ranking,
            trust_basis=MemoryTrustBasis.HUMAN_APPROVAL,
        ),
    )
    assert _build(items=items, evidence=evidence).confidence == 0.5


def test_records_and_evidence_must_align_without_reordering() -> None:
    first = _item()
    second = _item(
        "record-2",
        memory_type=MemoryType.KNOWN_ISSUE,
        logical_key="issue:2",
    )
    first_evidence = _evidence()
    second_evidence = _evidence(
        "record-2",
        memory_type=MemoryType.KNOWN_ISSUE,
        logical_key="issue:2",
    )
    with pytest.raises(ValueError, match="align"):
        _build(
            items=(first, second),
            evidence=(second_evidence, first_evidence),
        )


def test_shared_record_fields_must_match() -> None:
    with pytest.raises(ValueError, match="align"):
        _build(evidence=(_evidence(logical_key="component:U2"),))


def test_duplicate_record_ids_are_rejected() -> None:
    duplicate_items = (
        _item(),
        _item(logical_key="component:duplicate"),
    )
    duplicate_evidence = (
        _evidence(),
        _evidence(logical_key="component:duplicate"),
    )
    with pytest.raises(ValueError, match="unique"):
        _build(items=duplicate_items, evidence=duplicate_evidence)


def test_unknown_tampered_trust_basis_is_rejected() -> None:
    evidence = _evidence()
    object.__setattr__(evidence, "trust_basis", "UNKNOWN")
    with pytest.raises(ValueError):
        _build(evidence=(evidence,))


def test_invalid_or_stale_fingerprint_is_rejected() -> None:
    context = _build()
    with pytest.raises(ValidationError):
        RankedMemoryContext(
            **context.model_dump(exclude={"context_fingerprint"}),
            context_fingerprint="sha256:" + "A" * 64,
        )
    with pytest.raises(ValidationError, match="fingerprint"):
        RankedMemoryContext(
            **context.model_dump(exclude={"context_fingerprint"}),
            context_fingerprint="sha256:" + "0" * 64,
        )


def test_builder_does_not_mutate_inputs_and_returns_deep_copies() -> None:
    item = _item()
    evidence = _evidence()
    item_before = item.model_dump_json()
    evidence_before = evidence.model_dump_json()

    context = build_memory_context((item,), evidence=(evidence,))

    assert item.model_dump_json() == item_before
    assert evidence.model_dump_json() == evidence_before
    assert context.records[0] == item
    assert context.evidence[0] == evidence
    assert context.records[0] is not item
    assert context.evidence[0] is not evidence
