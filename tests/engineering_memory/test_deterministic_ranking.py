from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_memory.context import MemoryRankingBreakdown
from embedded_copilot.engineering_memory.models import MemoryType
from embedded_copilot.engineering_memory.ranking import (
    RankedMemoryItem,
    rank_memories,
)


def _ranking(
    *,
    verification: int = 0,
    domain: int = 0,
    usage: int = 0,
    recency: int = 0,
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
    record_id: str,
    *,
    memory_type: MemoryType = MemoryType.COMPONENT,
    logical_key: str | None = None,
    ranking: MemoryRankingBreakdown | None = None,
) -> RankedMemoryItem:
    return RankedMemoryItem(
        record_id=record_id,
        memory_type=memory_type,
        logical_key=logical_key or f"component:{record_id}",
        ranking=_ranking() if ranking is None else ranking,
    )


def test_ranked_item_is_frozen_strict_and_forbids_extra_fields() -> None:
    item = _item("record-1")
    with pytest.raises(ValidationError):
        item.record_id = "record-2"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RankedMemoryItem(
            record_id="record-1",
            memory_type="COMPONENT",  # type: ignore[arg-type]
            logical_key="component:record-1",
            ranking=_ranking(),
        )
    with pytest.raises(ValidationError):
        RankedMemoryItem(
            record_id="record-1",
            memory_type=MemoryType.COMPONENT,
            logical_key="component:record-1",
            ranking=_ranking(),
            unexpected="value",  # type: ignore[call-arg]
        )


def test_total_score_is_the_primary_descending_key() -> None:
    lower = _item("record-lower", ranking=_ranking(recency=100))
    higher = _item("record-higher", ranking=_ranking(recency=1000))
    assert rank_memories((lower, higher)) == (higher, lower)


@pytest.mark.parametrize(
    ("preferred_ranking", "other_ranking"),
    (
        (
            _ranking(verification=1000),
            _ranking(domain=1000, usage=500),
        ),
        (
            _ranking(domain=1000),
            _ranking(usage=1000, recency=1000),
        ),
        (
            _ranking(usage=500),
            _ranking(recency=1000),
        ),
        (
            _ranking(recency=109),
            _ranking(recency=100),
        ),
    ),
)
def test_factor_ties_use_each_factor_in_descending_order(
    preferred_ranking: MemoryRankingBreakdown,
    other_ranking: MemoryRankingBreakdown,
) -> None:
    assert preferred_ranking.total_millis == other_ranking.total_millis
    preferred = _item("record-preferred", ranking=preferred_ranking)
    other = _item("record-other", ranking=other_ranking)
    assert rank_memories((other, preferred)) == (preferred, other)


def test_memory_type_value_is_the_first_ascending_identity_key() -> None:
    component = _item("record-component", memory_type=MemoryType.COMPONENT)
    board = _item("record-board", memory_type=MemoryType.BOARD_PROFILE)
    assert rank_memories((component, board)) == (board, component)


def test_logical_key_is_the_second_ascending_identity_key() -> None:
    later = _item("record-later", logical_key="component:z")
    earlier = _item("record-earlier", logical_key="component:a")
    assert rank_memories((later, earlier)) == (earlier, later)


def test_record_id_is_the_final_ascending_identity_key() -> None:
    later = _item("record-z", logical_key="component:shared")
    earlier = _item("record-a", logical_key="component:shared")
    assert rank_memories((later, earlier)) == (earlier, later)


def test_default_limit_is_eight() -> None:
    items = tuple(_item(f"record-{index:02d}") for index in range(10))
    assert len(rank_memories(items)) == 8


def test_custom_limit_is_applied_after_ordering() -> None:
    items = tuple(_item(f"record-{index}") for index in range(5, 0, -1))
    assert tuple(item.record_id for item in rank_memories(items, limit=3)) == (
        "record-1",
        "record-2",
        "record-3",
    )


@pytest.mark.parametrize("limit", (1, 50))
def test_limit_boundaries_are_accepted(limit: int) -> None:
    items = tuple(_item(f"record-{index:02d}") for index in range(60))
    assert len(rank_memories(items, limit=limit)) == limit


@pytest.mark.parametrize("limit", (0, -1, 51, True))
def test_invalid_limits_are_rejected(limit: int) -> None:
    with pytest.raises(ValueError, match="limit"):
        rank_memories((_item("record-1"),), limit=limit)


@pytest.mark.parametrize(
    "collection",
    (
        lambda item: [item],
        lambda item: {item},
        lambda item: (value for value in (item,)),
    ),
)
def test_input_collection_must_itself_be_a_tuple(
    collection: Callable[[RankedMemoryItem], object],
) -> None:
    with pytest.raises(ValueError, match="tuple"):
        rank_memories(collection(_item("record-1")))  # type: ignore[arg-type]


def test_duplicate_record_ids_are_rejected() -> None:
    first = _item("record-1", logical_key="component:first")
    duplicate = _item("record-1", logical_key="component:second")
    with pytest.raises(ValueError, match="unique"):
        rank_memories((first, duplicate))


def test_tampered_nested_ranking_is_revalidated() -> None:
    item = _item("record-1", ranking=_ranking(recency=1000))
    object.__setattr__(item.ranking, "total_millis", True)
    with pytest.raises(ValueError):
        rank_memories((item,))


def test_ranking_is_repeatable_without_mutating_or_recalculating_items() -> None:
    original = (
        _item("record-b", ranking=_ranking(domain=1000)),
        _item("record-a", ranking=_ranking(verification=1000)),
    )
    before = tuple(item.model_dump_json() for item in original)

    first = rank_memories(original)
    second = rank_memories(original)

    assert first == second
    assert tuple(item.model_dump_json() for item in original) == before
    assert first[0].ranking == original[1].ranking
    assert first[0] is not original[1]
    assert first[0].ranking is not original[1].ranking
