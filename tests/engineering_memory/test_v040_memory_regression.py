from __future__ import annotations

from datetime import UTC, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import (
    MemoryContext,
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryRetrievalRequest,
    MemoryTrustBasis,
)
from embedded_copilot.engineering_memory.exceptions import MemoryRetrievalUnavailable
from embedded_copilot.engineering_memory.models import MemoryStatus, MemoryType
from embedded_copilot.engineering_memory.ranking import rank_memories
from embedded_copilot.engineering_memory.retrieval import (
    create_engineering_memory_retriever,
)
from embedded_copilot.verification_agent import VerificationStatus

from .test_deterministic_ranking import _item, _ranking as _ordering_ranking
from .test_ranking import REQUESTED_AT, _evidence, _rank
from .test_retrieval_contracts import _context_values
from .test_retrieval_pipeline import _MemoryPort, _request, _verified_port
from .test_verified_read_projection import (
    _candidate_record,
    _history_page,
    _snapshot,
    _snapshot_record,
    _terminal_record,
    _verification_record,
)


def test_v040_contract_matrix_is_strict_frozen_and_deterministic() -> None:
    request = _request()
    context = MemoryContext(**_context_values())
    before = (request.model_dump_json(), context.model_dump_json())

    for contract in (
        MemoryRetrievalRequest,
        MemoryContext,
        MemoryContextEvidence,
        MemoryRankingBreakdown,
    ):
        assert contract.model_config["frozen"] is True
        assert contract.model_config["strict"] is True
        assert contract.model_config["extra"] == "forbid"
        assert contract.model_config["revalidate_instances"] == "always"

    with pytest.raises(ValidationError):
        request.limit = 4  # type: ignore[misc]
    with pytest.raises(ValidationError):
        MemoryRetrievalRequest(
            **{
                **request.model_dump(mode="python"),
                "domains": [MemoryDomain.HARDWARE],
            }
        )

    shifted = MemoryRetrievalRequest(
        **{
            **request.model_dump(mode="python"),
            "requested_at": request.requested_at.astimezone(
                timezone(timedelta(hours=8))
            ),
        }
    )
    assert shifted.requested_at.tzinfo is UTC
    assert (request.model_dump_json(), context.model_dump_json()) == before


def test_v040_retrieval_returns_only_complete_verified_context() -> None:
    retriever = create_engineering_memory_retriever(memory_port=_verified_port())
    request = _request()
    before = request.model_dump_json()

    first = retriever.retrieve(request)
    second = create_engineering_memory_retriever(
        memory_port=_verified_port()
    ).retrieve(request)

    assert tuple(item.status for item in first.records) == (MemoryStatus.VERIFIED,)
    assert tuple(item.record_id for item in first.records) == tuple(
        item.record_id for item in first.evidence
    )
    assert first.model_dump_json() == second.model_dump_json()
    assert request.model_dump_json() == before


@pytest.mark.parametrize(
    "record",
    (
        _candidate_record(),
        _verification_record(result_status=VerificationStatus.FAIL),
        _terminal_record(MemoryStatus.REVOKED),
        _terminal_record(MemoryStatus.SUPERSEDED),
    ),
)
def test_v040_retrieval_rejects_every_non_verified_state(record: object) -> None:
    port = _MemoryPort(
        snapshot=_snapshot(_snapshot_record(record)),  # type: ignore[arg-type]
        history_pages=(_history_page(record),),  # type: ignore[arg-type]
    )

    with pytest.raises(MemoryRetrievalUnavailable):
        create_engineering_memory_retriever(memory_port=port).retrieve(_request())


def test_v040_retrieval_revision_or_history_mismatch_fails_without_partial_data() -> None:
    first = _verification_record(record_id="record-1")
    second = _verification_record(record_id="record-2")
    cases = (
        _MemoryPort(
            snapshot=_snapshot(
                _snapshot_record(first),
                aggregate_revision=3,
            ),
            history_pages=(_history_page(first, aggregate_revision=2),),
        ),
        _MemoryPort(
            snapshot=_snapshot(
                _snapshot_record(first),
                _snapshot_record(second, logical_key="component:tampered"),
            ),
            history_pages=(_history_page(first, second),),
        ),
    )

    for port in cases:
        with pytest.raises(MemoryRetrievalUnavailable):
            create_engineering_memory_retriever(memory_port=port).retrieve(_request())


def test_v040_ranking_factor_boundaries_are_locked() -> None:
    assert _rank().verification_millis == 1000
    assert _rank(
        evidence=_evidence(trust_basis=MemoryTrustBasis.HUMAN_APPROVAL)
    ).verification_millis == 500
    assert tuple(
        _rank(domain_match=domain).domain_millis
        for domain in (MemoryDomain.HARDWARE, MemoryDomain.GENERAL, None)
    ) == (1000, 500, 0)
    assert tuple(_rank(usage_count=count).usage_millis for count in (0, 20, 21)) == (
        0,
        1000,
        1000,
    )
    assert tuple(
        _rank(
            evidence=_evidence(last_transition_at=REQUESTED_AT - age)
        ).recency_millis
        for age in (
            timedelta(days=30),
            timedelta(days=30, microseconds=1),
            timedelta(days=180),
            timedelta(days=180, microseconds=1),
            timedelta(days=365),
            timedelta(days=365, microseconds=1),
        )
    ) == (1000, 700, 700, 400, 400, 100)


@pytest.mark.parametrize(
    ("preferred", "other"),
    (
        (
            _item("preferred", ranking=_ordering_ranking(verification=1000)),
            _item(
                "other",
                ranking=_ordering_ranking(domain=1000, usage=500),
            ),
        ),
        (
            _item("preferred", ranking=_ordering_ranking(domain=1000)),
            _item(
                "other",
                ranking=_ordering_ranking(usage=1000, recency=1000),
            ),
        ),
        (
            _item("preferred", ranking=_ordering_ranking(usage=500)),
            _item("other", ranking=_ordering_ranking(recency=1000)),
        ),
        (
            _item("preferred", ranking=_ordering_ranking(recency=109)),
            _item("other", ranking=_ordering_ranking(recency=100)),
        ),
        (
            _item("preferred", memory_type=MemoryType.BOARD_PROFILE),
            _item("other", memory_type=MemoryType.COMPONENT),
        ),
        (
            _item("preferred", logical_key="component:a"),
            _item("other", logical_key="component:z"),
        ),
        (
            _item("record-a", logical_key="component:shared"),
            _item("record-z", logical_key="component:shared"),
        ),
    ),
)
def test_v040_ranking_tie_break_is_complete_and_repeatable(
    preferred: object,
    other: object,
) -> None:
    inputs = (other, preferred)
    first = rank_memories(inputs)  # type: ignore[arg-type]
    second = rank_memories(inputs)  # type: ignore[arg-type]
    assert first == second
    assert first[0] == preferred

