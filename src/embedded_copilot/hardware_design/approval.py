from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    safe_optional_text,
)


class DesignApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    REVIEWING = "REVIEWING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class DesignApproval(HardwareDesignModel):
    status: DesignApprovalStatus = DesignApprovalStatus.PROPOSED
    revision: int = Field(default=1, ge=1)
    feedback_summary: str | None = None

    @field_validator("feedback_summary", mode="before")
    @classmethod
    def validate_feedback(cls, value: object) -> str | None:
        return safe_optional_text(value, field="feedback_summary")
