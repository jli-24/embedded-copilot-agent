from __future__ import annotations

from pydantic import ValidationError
import pytest

from embedded_copilot.model_runtime.contracts import (
    ModelArtifactType,
    ModelRequest,
    ModelResponse,
    ModelTaskType,
    model_request_fingerprint,
    model_response_fingerprint,
)
from embedded_copilot.model_runtime.adapters.fake import FakeModelRuntimePort
from embedded_copilot.model_runtime.exceptions import ModelRuntimeUnavailable


def _request() -> ModelRequest:
    return ModelRequest.create(
        task_type=ModelTaskType.GENERATION,
        artifact_type=ModelArtifactType.FIRMWARE,
        context_projection=("project:demo", "stage:proposal"),
        engineering_constraints=("proposal_only",),
    )


def test_model_request_is_strict_frozen_and_deterministic() -> None:
    request = _request()
    assert request.model_config["strict"] is True
    assert request.model_config["extra"] == "forbid"
    assert model_request_fingerprint(request) == request.fingerprint
    with pytest.raises(ValidationError):
        request.context_projection += ("changed",)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ModelRequest.model_validate({**request.model_dump(), "prompt": "secret"})


def test_model_response_fingerprint_and_fake_are_stable() -> None:
    request = _request()
    port = FakeModelRuntimePort()
    first = port.generate(request)
    second = port.generate(request)
    assert first == second
    assert model_response_fingerprint(first) == first.fingerprint
    assert "prompt" not in first.model_dump()
    assert "provider" not in first.model_dump()


def test_model_response_rejects_bool_confidence_and_tampering() -> None:
    response = ModelResponse.create(
        artifact_projection=("filename:main.c",),
        summary="Deterministic proposal.",
        confidence=0.5,
    )
    with pytest.raises(ValidationError):
        ModelResponse.model_validate({**response.model_dump(), "confidence": True})
    with pytest.raises(ValidationError):
        ModelResponse.model_validate({**response.model_dump(), "summary": "changed"})


def test_unconfigured_model_adapter_is_unavailable() -> None:
    from embedded_copilot.model_runtime.adapters.local import LocalModelAdapter

    with pytest.raises(ModelRuntimeUnavailable, match="MODEL_UNAVAILABLE"):
        LocalModelAdapter().generate(_request())
