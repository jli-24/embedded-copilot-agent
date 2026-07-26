from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.vision_runtime import ImageType, VisionRequest
from embedded_copilot.vision_runtime.providers import (
    ProviderVisionResponse,
    UnavailableVisionProvider,
    VisionCapability,
    VisionProviderUnavailable,
)


def _request() -> VisionRequest:
    return VisionRequest(
        session_id="session:1",
        reference_id="image:1",
        image_type=ImageType.UNKNOWN,
        instruction_summary="Review the reference metadata.",
    )


def test_unavailable_provider_exposes_only_vision_capability_and_safe_failure() -> None:
    provider = UnavailableVisionProvider()

    assert provider.provider_id == "unavailable"
    assert provider.supported_capabilities == (VisionCapability.VISION,)
    with pytest.raises(
        VisionProviderUnavailable,
        match=r"^vision provider is unavailable$",
    ):
        asyncio.run(
            provider.analyze(
                _request(),
                reference_summary="Registered image reference.",
            )
        )


def test_provider_response_accepts_only_safe_generation_metadata() -> None:
    response = ProviderVisionResponse(
        summary="Review the reference metadata.",
        metadata={
            "cached": False,
            "finish_reason": "stop",
            "latency_ms": 4.5,
        },
    )

    assert dict(response.metadata) == {
        "cached": False,
        "finish_reason": "stop",
        "latency_ms": 4.5,
    }
    with pytest.raises(ValidationError):
        ProviderVisionResponse(
            summary="Unsafe response.",
            metadata={"thinking": "hidden trace"},
        )
    with pytest.raises(ValidationError):
        ProviderVisionResponse(
            summary="Unsafe response.",
            raw_response={"diagnostics": "private"},
        )
