from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_execution import (
    EngineeringExecutionRequest,
    EngineeringExecutionType,
    ExecutionApprovalStatus,
    ExecutionFindingCode,
    create_engineering_execution_runtime,
)
from tests.engineering_execution.conftest import make_request


def test_facade_and_zero_argument_factory_are_narrow() -> None:
    runtime = create_engineering_execution_runtime()
    assert tuple(
        name
        for name in dir(runtime)
        if not name.startswith("_") and callable(getattr(runtime, name))
    ) == ("engineering_execution_port",)


def test_request_is_frozen_strict_utc_and_extra_forbidden(artifact_report) -> None:
    request = make_request(artifact_report)
    assert request.requested_at.tzinfo is not None
    with pytest.raises(ValidationError):
        request.execution_id = "changed"
    values = request.model_dump(mode="python")
    values["extra"] = True
    with pytest.raises(ValidationError):
        EngineeringExecutionRequest.model_validate(values)
    values = request.model_dump(mode="python")
    values["requested_at"] = datetime(2026, 8, 8, 9, 0)
    with pytest.raises(ValidationError):
        EngineeringExecutionRequest.model_validate(values)


def test_approval_pending_has_no_reviewer_and_expiry_is_reserved(
    artifact_report,
) -> None:
    request = make_request(
        artifact_report,
        approval_status=ExecutionApprovalStatus.PENDING,
    )
    assert request.approval_context.reviewer is None
    assert request.approval_context.reviewed_at is None
    assert ExecutionFindingCode.APPROVAL_EXPIRED.value == "APPROVAL_EXPIRED"


def test_execution_type_is_fixed() -> None:
    assert tuple(EngineeringExecutionType) == (
        EngineeringExecutionType.BUILD,
        EngineeringExecutionType.FLASH,
        EngineeringExecutionType.DEBUG,
    )
