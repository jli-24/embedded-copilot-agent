"""Structured feedback projection contracts."""

from embedded_copilot.human_loop.feedback.models import FeedbackPriority
from embedded_copilot.human_loop.feedback.projection import (
    FeedbackProjection,
    FeedbackProjectionRequest,
)

__all__ = (
    "FeedbackPriority",
    "FeedbackProjection",
    "FeedbackProjectionRequest",
)
