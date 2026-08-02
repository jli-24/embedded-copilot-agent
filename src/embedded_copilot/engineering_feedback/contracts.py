"""Public Port for Engineering Feedback."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_feedback.integration.inputs import (
    EngineeringFeedbackRequest,
)
from embedded_copilot.engineering_feedback.models import EngineeringFeedbackReport


@runtime_checkable
class EngineeringFeedbackPort(Protocol):
    def submit_feedback(
        self,
        request: EngineeringFeedbackRequest,
    ) -> EngineeringFeedbackReport: ...
