from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.memory_automation.contracts import MemoryCandidate, MemoryReviewStatus, MemoryType


class MemoryWebContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class MemoryCandidateView(MemoryWebContract):
    memory_id: str
    memory_type: MemoryType
    source_reference: str
    confidence: float
    review_status: MemoryReviewStatus
    fingerprint: str
    title: str
    summary: str
    tags: tuple[str, ...]

    @classmethod
    def from_candidate(cls, candidate: MemoryCandidate) -> "MemoryCandidateView":
        checked = MemoryCandidate.model_validate(candidate.model_copy(deep=True))
        return cls(
            memory_id=checked.memory_id,
            memory_type=checked.memory_type,
            source_reference=checked.source.source_reference,
            confidence=checked.confidence,
            review_status=checked.review_status,
            fingerprint=checked.fingerprint,
            title=checked.title,
            summary=checked.summary,
            tags=checked.tags,
        )


class MemoryCandidateListResponse(MemoryWebContract):
    candidates: tuple[MemoryCandidateView, ...]

    @field_validator("candidates", mode="before")
    @classmethod
    def tuple_only(cls, value: object) -> object:
        if not isinstance(value, tuple):
            raise ValueError("candidates must be a tuple")
        return value


class MemoryApprovalRequest(MemoryWebContract):
    memory_id: str
    candidate_fingerprint: str
    reviewer: str
    decision: Literal["APPROVED", "REJECTED"]
    reviewed_at: datetime

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def parse_timestamp(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("reviewed_at is invalid") from error
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> "MemoryApprovalRequest":
        from embedded_copilot.memory_automation.contracts import MemoryApprovalProjection

        MemoryApprovalProjection(
            memory_id=self.memory_id,
            candidate_fingerprint=self.candidate_fingerprint,
            reviewer=self.reviewer,
            decision=self.decision,
            reviewed_at=self.reviewed_at,
        )
        return self


class MemoryEventResponse(MemoryWebContract):
    event_type: str
    memory_id: str
    review_status: MemoryReviewStatus
