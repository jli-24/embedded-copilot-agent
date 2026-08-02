"""Stateless conversation feedback projection service."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.conversation_feedback.contracts import ConversationFeedbackPort
from embedded_copilot.conversation_feedback.exceptions import FeedbackRejected
from embedded_copilot.conversation_feedback.models import (
    ConversationFeedbackProjection,
    UserFeedback,
    conversation_feedback_fingerprint,
)
from embedded_copilot.engineering_events import (
    EngineeringEvent,
    EngineeringEventType,
    engineering_event_fingerprint,
)


class ConversationFeedbackService:
    __slots__ = ()

    def feedback_port(self) -> ConversationFeedbackPort:
        return self

    def project(self, feedback: UserFeedback) -> ConversationFeedbackProjection:
        checked = _typed_copy(feedback)
        event_values = dict(
            sequence=1,
            event_type=EngineeringEventType.USER_FEEDBACK,
            stage="CONVERSATION_FEEDBACK",
            status="RECORDED",
            count=1,
            reference_id=checked.feedback_id,
            timestamp=checked.timestamp,
        )
        event = EngineeringEvent(
            **event_values,
            fingerprint=engineering_event_fingerprint(**event_values),
        )
        values = dict(
            feedback_id=checked.feedback_id,
            session_id=checked.session_id,
            target_agent=checked.target_agent,
            feedback_type=checked.feedback_type,
            event=event,
        )
        return ConversationFeedbackProjection(
            **values,
            fingerprint=conversation_feedback_fingerprint(**values),
        )


def create_conversation_feedback_service() -> ConversationFeedbackService:
    return ConversationFeedbackService()


def _typed_copy(value: object) -> UserFeedback:
    if type(value) is not UserFeedback:
        raise FeedbackRejected("feedback request was rejected") from None
    try:
        return UserFeedback.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise FeedbackRejected("feedback request was rejected") from None

