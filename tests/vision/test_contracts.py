from __future__ import annotations

import asyncio
import inspect
from typing import get_type_hints

import pytest
from pydantic import ValidationError

import embedded_copilot.vision_runtime as public_runtime
from embedded_copilot.vision_runtime import (
    ImageType,
    VisionPort,
    VisionRequest,
    VisionResponse,
    VisionRuntime,
    create_vision_runtime,
)


class _Vision:
    async def analyze(self, request: VisionRequest) -> VisionResponse:
        return VisionResponse(summary=f"Review reference {request.reference_id}.")


def _request() -> VisionRequest:
    return VisionRequest(
        session_id="session:1",
        reference_id="image:1",
        image_type=ImageType.UNKNOWN,
        instruction_summary="Review the registered image reference.",
    )


def test_vision_request_is_frozen_and_rejects_payload_or_infrastructure_fields() -> None:
    request = _request()

    assert tuple(type(request).model_fields) == (
        "session_id",
        "reference_id",
        "image_type",
        "instruction_summary",
    )
    with pytest.raises(ValidationError):
        VisionRequest(
            **request.model_dump(),
            content="forbidden",
        )
    with pytest.raises(ValidationError):
        request.reference_id = "image:2"


def test_vision_response_is_a_review_required_reasoning_suggestion() -> None:
    response = VisionResponse(summary="Review the referenced metadata.")

    assert response.model_dump(mode="json") == {
        "output_type": "reasoning_suggestion",
        "summary": "Review the referenced metadata.",
        "review_required": True,
    }
    with pytest.raises(ValidationError):
        VisionResponse(
            summary="Unsafe lifecycle output.",
            evidence={"fact": "invented"},
        )


def test_vision_port_is_model_agnostic() -> None:
    signature = inspect.signature(VisionPort.analyze)

    assert tuple(signature.parameters) == ("self", "request")
    assert all(
        name not in signature.parameters
        for name in ("model", "provider", "endpoint", "credential")
    )


def test_vision_runtime_facade_only_exposes_the_protocol_port() -> None:
    vision = _Vision()

    with pytest.raises(TypeError, match="composition factory"):
        VisionRuntime(vision)
    runtime = VisionRuntime._compose(vision)

    assert isinstance(runtime.vision_port(), VisionPort)
    assert asyncio.run(runtime.vision_port().analyze(_request())).review_required
    assert get_type_hints(VisionRuntime.vision_port)["return"] is VisionPort
    for forbidden in (
        "provider",
        "router",
        "registry",
        "configuration",
        "settings",
        "config",
        "health",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.vision_port(), forbidden)


def test_vision_runtime_package_exports_only_stable_contracts_and_facade() -> None:
    assert public_runtime.__all__ == [
        "ImageType",
        "VisionPort",
        "VisionRequest",
        "VisionResponse",
        "VisionRuntime",
        "create_vision_runtime",
    ]
