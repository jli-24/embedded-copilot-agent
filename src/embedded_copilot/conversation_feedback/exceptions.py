"""Sanitized Conversation Feedback exceptions."""


class ConversationFeedbackError(Exception):
    """Base exception for feedback projection failures."""


class FeedbackRejected(ConversationFeedbackError):
    """Raised when caller-owned feedback fails validation."""

