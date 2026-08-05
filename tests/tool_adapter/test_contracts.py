import pytest
from pydantic import ValidationError

from embedded_copilot.tool_adapter.contracts import (
    ToolCapabilitySnapshot,
    ToolCapabilityStatus,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolType,
    validate_execution_request,
)


def _request() -> ToolExecutionRequest:
    return ToolExecutionRequest.create(
        tool_type=ToolType.ESP_IDF,
        operation="build",
        workspace_reference="workspace-1",
        artifact_reference="artifact-1",
        approval_reference="approval-1",
    )


def test_request_is_frozen_strict_and_fingerprint_bound() -> None:
    request = _request()
    with pytest.raises(ValidationError):
        request.operation = "flash"  # type: ignore[misc]
    assert validate_execution_request(request) == request
    with pytest.raises(ValidationError):
        ToolExecutionRequest.model_validate({**request.model_dump(), "extra": "x"})
    with pytest.raises(ValidationError):
        ToolExecutionRequest.model_validate(
            {**request.model_dump(), "fingerprint": "sha256:" + "0" * 64}
        )


def test_collections_are_native_tuples_and_capability_is_deterministic() -> None:
    capability = ToolCapabilitySnapshot.create(
        tool_name="ESP-IDF",
        version="5.2",
        capabilities=("build", "flash"),
        status=ToolCapabilityStatus.AVAILABLE,
    )
    assert type(capability.capabilities) is tuple
    assert capability == ToolCapabilitySnapshot.create(
        tool_name="ESP-IDF",
        version="5.2",
        capabilities=("build", "flash"),
        status=ToolCapabilityStatus.AVAILABLE,
    )


def test_result_rejects_sensitive_summary() -> None:
    with pytest.raises(ValidationError):
        ToolExecutionResult.create(
            status=ToolExecutionStatus.SUCCESS,
            tool_type=ToolType.ESP_IDF,
            operation="build",
            artifact_reference="artifact-1",
            summary="token: secret",
        )
