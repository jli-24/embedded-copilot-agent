from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import (
    MemoryContext,
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryRetrievalBinding,
    MemoryRetrievalRequest,
    MemoryTrustBasis,
    MemoryUsageSignal,
)
from embedded_copilot.engineering_memory.exceptions import (
    EngineeringMemoryError,
    MemoryRetrievalError,
    MemoryRetrievalRequestRejected,
    MemoryRetrievalUnavailable,
)
from embedded_copilot.engineering_memory.fingerprint import canonical_fingerprint
from embedded_copilot.engineering_memory.models import (
    BoardProfileMemory,
    MemoryProvenance,
    MemorySnapshotRecord,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from embedded_copilot.verification_agent import VerificationSubjectType

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
FINGERPRINT_A = "sha256:" + "a" * 64
FINGERPRINT_B = "sha256:" + "b" * 64


def _usage(record_id: str = "record-1", usage_count: int = 2) -> MemoryUsageSignal:
    return MemoryUsageSignal(record_id=record_id, usage_count=usage_count)


def _binding_values(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "request_id": "request-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "caller": "supervisor-1",
        "requested_at": UTC_TIME,
        "usage_signals": (),
        "limit": 8,
    }
    values.update(changes)
    return values


def _record(record_id: str = "record-1") -> MemorySnapshotRecord:
    return MemorySnapshotRecord(
        record_id=record_id,
        memory_type=MemoryType.BOARD_PROFILE,
        logical_key="board-profile",
        payload=BoardProfileMemory(
            board_id="board-1",
            board_name="Sensor Board",
            mcu_family="STM32",
            mcu_model="STM32F407VG",
            architecture="ARM Cortex-M4",
        ),
        provenance=MemoryProvenance(
            source_type=MemorySourceType.VERIFICATION_RESULT,
            source_reference="verification-1",
            source_revision="revision-1",
            created_by="reviewer-1",
            observed_at=UTC_TIME,
        ),
        status=MemoryStatus.VERIFIED,
        record_revision=1,
    )


def _ranking(**changes: object) -> MemoryRankingBreakdown:
    values: dict[str, object] = {
        "verification_millis": 1000,
        "domain_millis": 1000,
        "usage_millis": 100,
        "recency_millis": 1000,
        "total_millis": 820,
        "relevance_score": 0.82,
    }
    values.update(changes)
    return MemoryRankingBreakdown(**values)


def _evidence(
    record_id: str = "record-1",
    *,
    trust_basis: MemoryTrustBasis = MemoryTrustBasis.VERIFICATION,
) -> MemoryContextEvidence:
    verification_subject = (
        VerificationSubjectType.HARDWARE
        if trust_basis is MemoryTrustBasis.VERIFICATION
        else None
    )
    verification_confidence = (
        1.0 if trust_basis is MemoryTrustBasis.VERIFICATION else None
    )
    return MemoryContextEvidence(
        record_id=record_id,
        memory_type=MemoryType.BOARD_PROFILE,
        logical_key="board-profile",
        trust_basis=trust_basis,
        verification_subject=verification_subject,
        verification_confidence=verification_confidence,
        provenance_source_type=MemorySourceType.VERIFICATION_RESULT,
        provenance_reference="verification-1",
        last_transition_at=UTC_TIME,
        ranking=_ranking(),
    )


def _context_values(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "request_id": "request-1",
        "project_id": "project-1",
        "memory_id": "memory-1",
        "aggregate_revision": 1,
        "domains": (MemoryDomain.HARDWARE,),
        "records": (_record(),),
        "evidence": (_evidence(),),
        "confidence": 1.0,
        "source_snapshot_fingerprint": FINGERPRINT_A,
        "context_fingerprint": FINGERPRINT_B,
    }
    values.update(changes)
    return values


def test_retrieval_contracts_are_frozen_strict_and_forbid_extra() -> None:
    signal = _usage()
    with pytest.raises(ValidationError):
        signal.usage_count = 3
    with pytest.raises(ValidationError):
        MemoryUsageSignal(record_id="record-1", usage_count="2")
    with pytest.raises(ValidationError):
        MemoryUsageSignal(record_id="record-1", usage_count=2, unexpected=True)
    for contract in (
        MemoryUsageSignal,
        MemoryRetrievalBinding,
        MemoryRetrievalRequest,
        MemoryRankingBreakdown,
        MemoryContextEvidence,
        MemoryContext,
    ):
        assert contract.model_config == {
            "frozen": True,
            "strict": True,
            "extra": "forbid",
            "hide_input_in_errors": True,
            "revalidate_instances": "always",
        }
    assert tuple(MemoryUsageSignal.model_fields) == ("record_id", "usage_count")
    assert tuple(MemoryRetrievalBinding.model_fields) == (
        "request_id",
        "project_id",
        "memory_id",
        "caller",
        "requested_at",
        "usage_signals",
        "limit",
    )
    assert tuple(MemoryRetrievalRequest.model_fields) == (
        *tuple(MemoryRetrievalBinding.model_fields),
        "domains",
    )
    assert tuple(MemoryRankingBreakdown.model_fields) == (
        "verification_millis",
        "domain_millis",
        "usage_millis",
        "recency_millis",
        "total_millis",
        "relevance_score",
    )
    assert tuple(MemoryContextEvidence.model_fields) == (
        "record_id",
        "memory_type",
        "logical_key",
        "trust_basis",
        "verification_subject",
        "verification_confidence",
        "provenance_source_type",
        "provenance_reference",
        "last_transition_at",
        "ranking",
    )
    assert tuple(MemoryContext.model_fields) == (
        "request_id",
        "project_id",
        "memory_id",
        "aggregate_revision",
        "domains",
        "records",
        "evidence",
        "confidence",
        "source_snapshot_fingerprint",
        "context_fingerprint",
    )


def test_retrieval_binding_requires_utc_and_stable_usage_signals() -> None:
    plus_eight = datetime(2026, 7, 30, 11, 0, tzinfo=timezone(timedelta(hours=8)))
    binding = MemoryRetrievalBinding(
        **_binding_values(
            requested_at=plus_eight,
            usage_signals=(_usage("record-2"), _usage("record-1")),
        )
    )
    assert binding.requested_at == UTC_TIME
    assert binding.requested_at.tzinfo is UTC
    assert tuple(item.record_id for item in binding.usage_signals) == (
        "record-1",
        "record-2",
    )
    with pytest.raises(ValidationError, match="timezone aware"):
        MemoryRetrievalBinding(
            **_binding_values(requested_at=datetime(2026, 7, 30, 3, 0))  # noqa: DTZ001
        )
    with pytest.raises(ValidationError, match="unique"):
        MemoryRetrievalBinding(
            **_binding_values(usage_signals=(_usage(), _usage()))
        )
    with pytest.raises(ValidationError):
        MemoryRetrievalBinding(**_binding_values(limit=True))
    with pytest.raises(ValidationError):
        MemoryRetrievalBinding(**_binding_values(limit=51))


@pytest.mark.parametrize(
    "value",
    [
        [_usage()],
        {_usage()},
        (_usage() for _ in range(1)),
    ],
)
def test_collection_inputs_must_be_tuples(value: object) -> None:
    with pytest.raises(ValidationError, match="tuple"):
        MemoryRetrievalBinding(**_binding_values(usage_signals=value))
    with pytest.raises(ValidationError, match="tuple"):
        MemoryRetrievalRequest(
            **_binding_values(),
            domains=value,
        )
    with pytest.raises(ValidationError, match="tuple"):
        MemoryContext(**_context_values(records=value))


def test_retrieval_request_requires_unique_sorted_domains() -> None:
    request = MemoryRetrievalRequest(
        **_binding_values(),
        domains=tuple(reversed(tuple(MemoryDomain))),
    )
    assert request.domains == tuple(sorted(MemoryDomain, key=lambda item: item.value))
    assert tuple(MemoryDomain) == (
        MemoryDomain.FIRMWARE,
        MemoryDomain.HARDWARE,
        MemoryDomain.PCB,
        MemoryDomain.DEBUG,
        MemoryDomain.GENERAL,
    )
    assert tuple(MemoryTrustBasis) == (
        MemoryTrustBasis.VERIFICATION,
        MemoryTrustBasis.HUMAN_APPROVAL,
    )
    with pytest.raises(ValidationError, match="non-empty"):
        MemoryRetrievalRequest(**_binding_values(), domains=())
    with pytest.raises(ValidationError, match="unique"):
        MemoryRetrievalRequest(
            **_binding_values(),
            domains=(MemoryDomain.DEBUG, MemoryDomain.DEBUG),
        )


def test_bool_is_not_a_usage_count_or_ranking_integer() -> None:
    with pytest.raises(ValidationError):
        MemoryUsageSignal(record_id="record-1", usage_count=True)
    for field_name in (
        "verification_millis",
        "domain_millis",
        "usage_millis",
        "recency_millis",
        "total_millis",
    ):
        with pytest.raises(ValidationError):
            _ranking(**{field_name: True})


def test_nested_instances_are_revalidated_after_tampering() -> None:
    signal = _usage()
    object.__setattr__(signal, "usage_count", True)
    with pytest.raises(ValidationError):
        MemoryRetrievalBinding(**_binding_values(usage_signals=(signal,)))

    ranking = _ranking()
    object.__setattr__(ranking, "total_millis", True)
    with pytest.raises(ValidationError):
        MemoryContextEvidence(
            **_evidence().model_dump(exclude={"ranking"}),
            ranking=ranking,
        )


def test_deterministic_serialization_and_generic_fingerprint_stability() -> None:
    first = MemoryRetrievalRequest(
        **_binding_values(usage_signals=(_usage("record-2"), _usage("record-1"))),
        domains=(MemoryDomain.PCB, MemoryDomain.FIRMWARE),
    )
    second = MemoryRetrievalRequest(
        **dict(reversed(tuple(first.model_dump(mode="python").items())))
    )
    assert first.model_dump_json() == second.model_dump_json()
    assert canonical_fingerprint(first) == canonical_fingerprint(second)


@pytest.mark.parametrize(
    "field_name",
    ["source_snapshot_fingerprint", "context_fingerprint"],
)
def test_context_fingerprints_only_accept_canonical_sha256_format(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        MemoryContext(**_context_values(**{field_name: "sha256:" + "A" * 64}))
    with pytest.raises(ValidationError):
        MemoryContext(**_context_values(**{field_name: "not-a-fingerprint"}))


def test_records_and_evidence_preserve_rank_order_and_align() -> None:
    records = (_record("record-2"), _record("record-1"))
    evidence = (_evidence("record-2"), _evidence("record-1"))
    context = MemoryContext(**_context_values(records=records, evidence=evidence))
    assert tuple(item.record_id for item in context.records) == (
        "record-2",
        "record-1",
    )
    assert tuple(item.record_id for item in context.evidence) == (
        "record-2",
        "record-1",
    )
    with pytest.raises(ValidationError, match="align"):
        MemoryContext(
            **_context_values(records=records, evidence=tuple(reversed(evidence)))
        )
    with pytest.raises(ValidationError, match="unique"):
        MemoryContext(
            **_context_values(
                records=(_record(), _record()),
                evidence=(_evidence(), _evidence()),
            )
        )


def test_context_confidence_matches_evidence_completeness() -> None:
    MemoryContext(**_context_values())
    with pytest.raises(ValidationError, match="confidence"):
        MemoryContext(**_context_values(confidence=0.5))
    approval_evidence = _evidence(
        trust_basis=MemoryTrustBasis.HUMAN_APPROVAL,
    )
    approved = MemoryContext(
        **_context_values(evidence=(approval_evidence,), confidence=0.5)
    )
    assert approved.confidence == 0.5
    empty = MemoryContext(
        **_context_values(
            aggregate_revision=0,
            records=(),
            evidence=(),
            confidence=0.0,
        )
    )
    assert empty.confidence == 0.0
    with pytest.raises(ValidationError, match="confidence"):
        MemoryContext(
            **_context_values(records=(), evidence=(), confidence=1.0)
        )


def test_ranking_and_evidence_confidence_constraints() -> None:
    with pytest.raises(ValidationError, match="consistent"):
        _ranking(relevance_score=0.81)
    with pytest.raises(ValidationError, match="consistent"):
        _ranking(total_millis=900, relevance_score=0.9)
    with pytest.raises(ValidationError):
        _ranking(total_millis=1001, relevance_score=1.001)
    with pytest.raises(ValidationError):
        MemoryContextEvidence(
            **_evidence().model_dump()
            | {"verification_confidence": float("nan")}
        )
    with pytest.raises(ValidationError, match="trust basis"):
        MemoryContextEvidence(
            **_evidence().model_dump()
            | {
                "trust_basis": MemoryTrustBasis.HUMAN_APPROVAL,
                "verification_subject": VerificationSubjectType.HARDWARE,
                "verification_confidence": 1.0,
            }
        )


def test_evidence_timestamp_requires_awareness_and_normalizes_to_utc() -> None:
    plus_eight = datetime(2026, 7, 30, 11, 0, tzinfo=timezone(timedelta(hours=8)))
    evidence = MemoryContextEvidence(
        **_evidence().model_dump() | {"last_transition_at": plus_eight}
    )
    assert evidence.last_transition_at == UTC_TIME
    assert evidence.last_transition_at.tzinfo is UTC
    with pytest.raises(ValidationError, match="timezone aware"):
        MemoryContextEvidence(
            **_evidence().model_dump()
            | {"last_transition_at": datetime(2026, 7, 30, 3, 0)}  # noqa: DTZ001
        )


def test_retrieval_exceptions_are_sanitized_and_fixed() -> None:
    rejected = MemoryRetrievalRequestRejected()
    unavailable = MemoryRetrievalUnavailable()
    assert isinstance(rejected, MemoryRetrievalError)
    assert isinstance(unavailable, MemoryRetrievalError)
    assert isinstance(rejected, EngineeringMemoryError)
    assert str(rejected) == "MEMORY_RETRIEVAL_REQUEST_REJECTED"
    assert str(unavailable) == "MEMORY_RETRIEVAL_UNAVAILABLE"
