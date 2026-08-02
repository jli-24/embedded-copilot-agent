from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from embedded_copilot.engineering_memory.context import (
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryTrustBasis,
    MemoryUsageSignal,
)
from embedded_copilot.engineering_memory.models import (
    MemorySourceType,
    MemoryType,
)
from embedded_copilot.engineering_memory.ranking import rank_memory
from embedded_copilot.verification_agent import VerificationSubjectType

REQUESTED_AT = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)


def _zero_ranking() -> MemoryRankingBreakdown:
    return MemoryRankingBreakdown(
        verification_millis=0,
        domain_millis=0,
        usage_millis=0,
        recency_millis=0,
        total_millis=0,
        relevance_score=0.0,
    )


def _evidence(
    *,
    trust_basis: MemoryTrustBasis = MemoryTrustBasis.VERIFICATION,
    last_transition_at: datetime = REQUESTED_AT,
) -> MemoryContextEvidence:
    verified = trust_basis is MemoryTrustBasis.VERIFICATION
    return MemoryContextEvidence(
        record_id="record-1",
        memory_type=MemoryType.COMPONENT,
        logical_key="component:U1",
        trust_basis=trust_basis,
        verification_subject=(
            VerificationSubjectType.HARDWARE if verified else None
        ),
        verification_confidence=1.0 if verified else None,
        provenance_source_type=MemorySourceType.VERIFICATION_RESULT,
        provenance_reference="verification-1",
        last_transition_at=last_transition_at,
        ranking=_zero_ranking(),
    )


def _rank(
    *,
    evidence: MemoryContextEvidence | None = None,
    domain_match: MemoryDomain | None = None,
    usage_count: int | None = None,
    requested_at: datetime = REQUESTED_AT,
) -> MemoryRankingBreakdown:
    usage_signal = (
        None
        if usage_count is None
        else MemoryUsageSignal(record_id="record-1", usage_count=usage_count)
    )
    return rank_memory(
        evidence=_evidence() if evidence is None else evidence,
        domain_match=domain_match,
        usage_signal=usage_signal,
        requested_at=requested_at,
    )


@pytest.mark.parametrize(
    ("trust_basis", "expected"),
    (
        (MemoryTrustBasis.VERIFICATION, 1000),
        (MemoryTrustBasis.HUMAN_APPROVAL, 500),
    ),
)
def test_verification_factor_uses_read_side_completeness(
    trust_basis: MemoryTrustBasis,
    expected: int,
) -> None:
    result = _rank(evidence=_evidence(trust_basis=trust_basis))
    assert result.verification_millis == expected


@pytest.mark.parametrize(
    ("domain_match", "expected"),
    (
        (MemoryDomain.HARDWARE, 1000),
        (MemoryDomain.GENERAL, 500),
        (None, 0),
    ),
)
def test_domain_factor_has_exact_general_and_no_match_states(
    domain_match: MemoryDomain | None,
    expected: int,
) -> None:
    assert _rank(domain_match=domain_match).domain_millis == expected


@pytest.mark.parametrize(
    ("usage_count", "expected"),
    (
        (None, 0),
        (0, 0),
        (1, 50),
        (19, 950),
        (20, 1000),
        (21, 1000),
        (1000, 1000),
    ),
)
def test_usage_factor_is_caller_owned_and_capped(
    usage_count: int | None,
    expected: int,
) -> None:
    assert _rank(usage_count=usage_count).usage_millis == expected


def test_usage_signal_must_bind_the_ranked_record() -> None:
    with pytest.raises(ValueError, match="record"):
        rank_memory(
            evidence=_evidence(),
            domain_match=None,
            usage_signal=MemoryUsageSignal(record_id="record-2", usage_count=1),
            requested_at=REQUESTED_AT,
        )


def test_tampered_bool_usage_is_revalidated() -> None:
    signal = MemoryUsageSignal(record_id="record-1", usage_count=1)
    object.__setattr__(signal, "usage_count", True)
    with pytest.raises(ValueError):
        rank_memory(
            evidence=_evidence(),
            domain_match=None,
            usage_signal=signal,
            requested_at=REQUESTED_AT,
        )


@pytest.mark.parametrize(
    ("age", "expected"),
    (
        (timedelta(0), 1000),
        (timedelta(days=30), 1000),
        (timedelta(days=30, microseconds=1), 700),
        (timedelta(days=180), 700),
        (timedelta(days=180, microseconds=1), 400),
        (timedelta(days=365), 400),
        (timedelta(days=365, microseconds=1), 100),
        (timedelta(days=1000), 100),
    ),
)
def test_recency_factor_uses_fixed_buckets(
    age: timedelta,
    expected: int,
) -> None:
    evidence = _evidence(last_transition_at=REQUESTED_AT - age)
    assert _rank(evidence=evidence).recency_millis == expected


def test_future_and_naive_timestamps_are_rejected() -> None:
    future = _evidence(last_transition_at=REQUESTED_AT + timedelta(microseconds=1))
    with pytest.raises(ValueError, match="future"):
        _rank(evidence=future)
    with pytest.raises(ValueError, match="timezone aware"):
        _rank(requested_at=datetime(2026, 7, 30, 3, 0))  # noqa: DTZ001


@pytest.mark.parametrize("invalid", (float("nan"), float("inf")))
def test_non_finite_tampered_evidence_is_rejected(invalid: float) -> None:
    evidence = _evidence()
    object.__setattr__(evidence, "verification_confidence", invalid)
    with pytest.raises(ValueError):
        _rank(evidence=evidence)


def test_total_uses_fixed_integer_formula() -> None:
    evidence = _evidence(last_transition_at=REQUESTED_AT - timedelta(days=31))
    result = _rank(
        evidence=evidence,
        domain_match=MemoryDomain.HARDWARE,
        usage_count=5,
    )
    assert result == MemoryRankingBreakdown(
        verification_millis=1000,
        domain_millis=1000,
        usage_millis=250,
        recency_millis=700,
        total_millis=820,
        relevance_score=0.82,
    )


def test_invalid_domain_match_is_rejected() -> None:
    with pytest.raises(ValueError, match="domain"):
        rank_memory(
            evidence=_evidence(),
            domain_match="HARDWARE",  # type: ignore[arg-type]
            usage_signal=None,
            requested_at=REQUESTED_AT,
        )


def test_ranking_is_repeatable_and_does_not_mutate_inputs() -> None:
    evidence = _evidence(last_transition_at=REQUESTED_AT - timedelta(days=31))
    usage = MemoryUsageSignal(record_id="record-1", usage_count=5)
    evidence_before = evidence.model_dump_json()
    usage_before = usage.model_dump_json()
    first = rank_memory(
        evidence=evidence,
        domain_match=MemoryDomain.GENERAL,
        usage_signal=usage,
        requested_at=REQUESTED_AT,
    )
    second = rank_memory(
        evidence=evidence,
        domain_match=MemoryDomain.GENERAL,
        usage_signal=usage,
        requested_at=REQUESTED_AT,
    )
    assert first == second
    assert evidence.model_dump_json() == evidence_before
    assert usage.model_dump_json() == usage_before
