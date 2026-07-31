from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, field_validator

from .context import (
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryTrustBasis,
    MemoryUsageSignal,
)
from .models import MemoryType, _identifier, _safe_reference

_THIRTY_DAYS = timedelta(days=30)
_ONE_HUNDRED_EIGHTY_DAYS = timedelta(days=180)
_THREE_HUNDRED_SIXTY_FIVE_DAYS = timedelta(days=365)


class RankedMemoryItem(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    record_id: str
    memory_type: MemoryType
    logical_key: str
    ranking: MemoryRankingBreakdown

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @field_validator("logical_key", mode="before")
    @classmethod
    def validate_logical_key(cls, value: object) -> str:
        return _safe_reference(value, field="logical_key")


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _checked_evidence(value: object) -> MemoryContextEvidence:
    if not isinstance(value, MemoryContextEvidence):
        raise ValueError("evidence is invalid")  # noqa: TRY004
    return MemoryContextEvidence.model_validate(copy.deepcopy(value))


def _checked_usage_signal(value: object) -> MemoryUsageSignal:
    if not isinstance(value, MemoryUsageSignal):
        raise ValueError("usage signal is invalid")  # noqa: TRY004
    return MemoryUsageSignal.model_validate(copy.deepcopy(value))


def _verification_factor(evidence: MemoryContextEvidence) -> int:
    if evidence.trust_basis is MemoryTrustBasis.VERIFICATION:
        return 1000
    return 500


def _domain_factor(domain_match: MemoryDomain | None) -> int:
    if domain_match is None:
        return 0
    if not isinstance(domain_match, MemoryDomain):
        raise ValueError("domain match is invalid")
    if domain_match is MemoryDomain.GENERAL:
        return 500
    return 1000


def _usage_factor(
    evidence: MemoryContextEvidence,
    usage_signal: MemoryUsageSignal | None,
) -> int:
    if usage_signal is None:
        return 0
    checked = _checked_usage_signal(usage_signal)
    if checked.record_id != evidence.record_id:
        raise ValueError("usage signal record does not match evidence")
    return min(checked.usage_count, 20) * 50


def _recency_factor(
    *,
    requested_at: datetime,
    last_transition_at: datetime,
) -> int:
    age = requested_at - last_transition_at
    if age < timedelta(0):
        raise ValueError("last transition timestamp is in the future")
    if age <= _THIRTY_DAYS:
        return 1000
    if age <= _ONE_HUNDRED_EIGHTY_DAYS:
        return 700
    if age <= _THREE_HUNDRED_SIXTY_FIVE_DAYS:
        return 400
    return 100


def rank_memory(
    *,
    evidence: MemoryContextEvidence,
    domain_match: MemoryDomain | None,
    usage_signal: MemoryUsageSignal | None,
    requested_at: datetime,
) -> MemoryRankingBreakdown:
    checked_evidence = _checked_evidence(evidence)
    checked_requested_at = _utc(
        copy.deepcopy(requested_at),
        field="requested_at",
    )
    checked_domain = copy.deepcopy(domain_match)

    verification_millis = _verification_factor(checked_evidence)
    domain_millis = _domain_factor(checked_domain)
    usage_millis = _usage_factor(checked_evidence, usage_signal)
    recency_millis = _recency_factor(
        requested_at=checked_requested_at,
        last_transition_at=checked_evidence.last_transition_at,
    )
    total_millis = (
        4 * verification_millis
        + 3 * domain_millis
        + 2 * usage_millis
        + recency_millis
    ) // 10
    return MemoryRankingBreakdown(
        verification_millis=verification_millis,
        domain_millis=domain_millis,
        usage_millis=usage_millis,
        recency_millis=recency_millis,
        total_millis=total_millis,
        relevance_score=total_millis / 1000,
    )


def _checked_ranked_item(value: object) -> RankedMemoryItem:
    if not isinstance(value, RankedMemoryItem):
        raise ValueError("ranked memory item is invalid")  # noqa: TRY004
    return RankedMemoryItem.model_validate(copy.deepcopy(value))


def _ranking_key(item: RankedMemoryItem) -> tuple[int | str, ...]:
    ranking = item.ranking
    return (
        -ranking.total_millis,
        -ranking.verification_millis,
        -ranking.domain_millis,
        -ranking.usage_millis,
        -ranking.recency_millis,
        item.memory_type.value,
        item.logical_key,
        item.record_id,
    )


def rank_memories(
    items: tuple[RankedMemoryItem, ...],
    *,
    limit: int = 8,
) -> tuple[RankedMemoryItem, ...]:
    if type(items) is not tuple:
        raise ValueError("items must be a tuple")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit is invalid")

    checked_items = tuple(_checked_ranked_item(item) for item in items)
    record_ids = tuple(item.record_id for item in checked_items)
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("ranked memory item record IDs must be unique")

    return tuple(sorted(checked_items, key=_ranking_key)[:limit])
