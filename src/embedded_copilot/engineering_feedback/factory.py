"""Composition entrypoint for Engineering Feedback."""

from embedded_copilot.engineering_feedback.facade import EngineeringFeedbackRuntime
from embedded_copilot.engineering_feedback.runtime import (
    _create_engineering_feedback_service,
)


def create_engineering_feedback_runtime() -> EngineeringFeedbackRuntime:
    return EngineeringFeedbackRuntime(_create_engineering_feedback_service())
