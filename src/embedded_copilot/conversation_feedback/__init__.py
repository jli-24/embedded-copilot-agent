"""Framework-independent conversation feedback projections."""

from embedded_copilot.conversation_feedback.contracts import ConversationFeedbackPort
from embedded_copilot.conversation_feedback.exceptions import (
    ConversationFeedbackError,
    FeedbackRejected,
)
from embedded_copilot.conversation_feedback.models import (
    ConversationFeedbackProjection,
    FeedbackType,
    UserFeedback,
    canonical_feedback_json,
    conversation_feedback_fingerprint,
    user_feedback_fingerprint,
)
from embedded_copilot.conversation_feedback.service import (
    ConversationFeedbackService,
    create_conversation_feedback_service,
)

__all__ = (
    "ConversationFeedbackError",
    "ConversationFeedbackPort",
    "ConversationFeedbackProjection",
    "ConversationFeedbackService",
    "FeedbackRejected",
    "FeedbackType",
    "UserFeedback",
    "canonical_feedback_json",
    "conversation_feedback_fingerprint",
    "create_conversation_feedback_service",
    "user_feedback_fingerprint",
)

