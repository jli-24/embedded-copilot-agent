"""Deterministic Product request integration for the local demo."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError

from embedded_copilot.product import (
    CreateProjectRequest,
    create_project_request_fingerprint,
)
from embedded_copilot.web_api import WebProjectCreateRequest

_DEMO_TIME = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


class DemoPreparationPort:
    """Project a Web request into a minimal public Product request."""

    __slots__ = ()

    def prepare(self, request: WebProjectCreateRequest) -> CreateProjectRequest:
        checked = _typed_copy(request, WebProjectCreateRequest)
        values = dict(
            project_id="demo-project",
            project_name="Embedded Copilot Demo Project",
            project_summary=checked.requirement[:512],
            session_id="demo-session",
            requirement=None,
            plan=None,
            context=None,
            hardware_proposal=None,
            firmware_proposal=None,
            validation_report=None,
            artifact_contract=None,
            execution_report=None,
            feedback_report=None,
            optimization_report=None,
            decisions=(),
            created_at=_DEMO_TIME,
        )
        return CreateProjectRequest(
            **values,
            fingerprint=create_project_request_fingerprint(**values),
        )


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise TypeError("typed demo request is required")
    try:
        return expected_type.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise ValueError("demo request is invalid") from None
