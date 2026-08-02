"""Conversation feedback projection Port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.conversation_feedback.models import (
    ConversationFeedbackProjection,
    UserFeedback,
)


@runtime_checkable
class ConversationFeedbackPort(Protocol):
    def project(self, feedback: UserFeedback) -> ConversationFeedbackProjection: ...

