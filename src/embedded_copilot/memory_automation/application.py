from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import MemoryApprovalProjection, MemoryCandidate, MemoryReviewStatus
from .exceptions import MemoryApprovalRejected


@runtime_checkable
class MemoryCandidatePort(Protocol):
    def list_candidates(self) -> tuple[MemoryCandidate, ...]: ...

    def get_candidate(self, memory_id: str) -> MemoryCandidate | None: ...


@runtime_checkable
class MemoryPromotionPort(Protocol):
    def promote(self, candidate: object, approval: MemoryApprovalProjection) -> object: ...


@runtime_checkable
class MemoryServicePort(Protocol):
    def list_candidates(self) -> tuple[MemoryCandidate, ...]: ...

    def approve(
        self, memory_id: str, approval: MemoryApprovalProjection
    ) -> MemoryApprovalOutcome: ...


@dataclass(frozen=True)
class MemoryApprovalOutcome:
    memory_id: str
    event_type: str
    review_status: MemoryReviewStatus


def _status_value(result: object) -> str:
    status = getattr(result, "status", None)
    value = getattr(status, "value", status)
    return value if isinstance(value, str) else ""


class MemoryApplicationService:
    __slots__ = ("_candidates", "_promotion", "_writer")

    def __init__(
        self,
        candidates: MemoryCandidatePort,
        promotion: MemoryPromotionPort,
        writer: object,
    ) -> None:
        if not isinstance(candidates, MemoryCandidatePort):
            raise TypeError("memory candidate port is invalid")
        if not isinstance(promotion, MemoryPromotionPort):
            raise TypeError("memory promotion port is invalid")
        self._candidates = candidates
        self._promotion = promotion
        self._writer = writer

    def list_candidates(self) -> tuple[MemoryCandidate, ...]:
        values = self._candidates.list_candidates()
        if not isinstance(values, tuple):
            raise MemoryApprovalRejected()
        return tuple(
            MemoryCandidate.model_validate(copy.deepcopy(value)) for value in values
        )

    def approve(
        self, memory_id: str, approval: MemoryApprovalProjection
    ) -> MemoryApprovalOutcome:
        candidate = self._candidates.get_candidate(memory_id)
        if candidate is None:
            raise MemoryApprovalRejected()
        checked = MemoryCandidate.model_validate(copy.deepcopy(candidate))
        decision = MemoryApprovalProjection.model_validate(copy.deepcopy(approval))
        if decision.memory_id != checked.memory_id:
            raise MemoryApprovalRejected()
        projection = self._promotion.promote(checked, decision)
        writer_method = getattr(self._writer, "write_approved_memory", None)
        if not callable(writer_method):
            writer_method = getattr(self._writer, "write_approved_projection", None)
        if not callable(writer_method):
            writer_method = getattr(self._writer, "write", None)
        if not callable(writer_method):
            raise MemoryApprovalRejected()
        result = writer_method(projection)
        status = _status_value(result)
        if status == "REJECTED":
            raise MemoryApprovalRejected()
        event_type = getattr(result, "event_type", None)
        if not isinstance(event_type, str):
            event_type = "MEMORY_UPDATED" if status == "UPDATED" else "MEMORY_CREATED"
        return MemoryApprovalOutcome(
            memory_id=checked.memory_id,
            event_type=event_type,
            review_status=MemoryReviewStatus.APPROVED,
        )


__all__ = (
    "MemoryApplicationService",
    "MemoryApprovalOutcome",
    "MemoryCandidatePort",
    "MemoryPromotionPort",
    "MemoryServicePort",
)
