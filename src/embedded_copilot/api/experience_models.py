from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from embedded_copilot.experience.existing_contracts import (
    safe_identifier,
    safe_optional_summary,
    utc_datetime,
)
from embedded_copilot.experience.models import (
    ExperienceContractModel,
    ReviewIntent,
    ReviewIntentAction,
)


class ReviewIntentRequest(ExperienceContractModel):
    intent_id: str
    artifact_id: str
    action: ReviewIntentAction
    comment_summary: str | None = None
    timestamp: datetime

    @field_validator("intent_id", "artifact_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("comment_summary", mode="before")
    @classmethod
    def validate_comment_summary(cls, value: object) -> str | None:
        return safe_optional_summary(value, field="comment_summary")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return utc_datetime(value, field="timestamp")

    def to_intent(self, session_id: str) -> ReviewIntent:
        return ReviewIntent(
            intent_id=self.intent_id,
            session_id=session_id,
            artifact_id=self.artifact_id,
            action=self.action,
            comment_summary=self.comment_summary,
            timestamp=self.timestamp,
        )
