from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from embedded_copilot.vision_runtime import ImageType, VisionRequest
from embedded_copilot.vision_runtime.providers import (
    ProviderVisionResponse,
    VisionCapability,
    VisionProviderUnavailable,
)
from embedded_copilot.vision_runtime.routing import (
    VisionProviderRegistry,
    VisionRouter,
)


@dataclass
class _Provider:
    provider_id: str
    supported_capabilities: tuple[VisionCapability, ...]
    outcome: str
    calls: int = 0

    async def analyze(
        self,
        request: VisionRequest,
        *,
        reference_summary: str,
    ) -> ProviderVisionResponse:
        self.calls += 1
        if self.outcome == "unavailable":
            raise VisionProviderUnavailable("vision provider is unavailable")
        return ProviderVisionResponse(
            summary=f"{self.provider_id}: {reference_summary}",
        )


def _request() -> VisionRequest:
    return VisionRequest(
        session_id="session:1",
        reference_id="image:1",
        image_type=ImageType.UNKNOWN,
        instruction_summary="Review the reference metadata.",
    )


def test_router_selects_the_first_registered_capability_match() -> None:
    first = _Provider("first", (VisionCapability.VISION,), "success")
    second = _Provider("second", (VisionCapability.VISION,), "success")
    router = VisionRouter(VisionProviderRegistry((first, second)))

    response = asyncio.run(
        router.analyze(
            _request(),
            reference_summary="Registered image reference.",
        )
    )

    assert response.summary == "first: Registered image reference."
    assert first.calls == 1
    assert second.calls == 0


def test_router_does_not_fallback_after_selected_provider_failure() -> None:
    first = _Provider("first", (VisionCapability.VISION,), "unavailable")
    second = _Provider("second", (VisionCapability.VISION,), "success")
    router = VisionRouter(VisionProviderRegistry((first, second)))

    with pytest.raises(VisionProviderUnavailable):
        asyncio.run(
            router.analyze(
                _request(),
                reference_summary="Registered image reference.",
            )
        )

    assert first.calls == 1
    assert second.calls == 0


def test_router_reports_unavailable_when_no_provider_matches() -> None:
    router = VisionRouter(VisionProviderRegistry(()))

    with pytest.raises(
        VisionProviderUnavailable,
        match=r"^vision provider is unavailable$",
    ):
        asyncio.run(
            router.analyze(
                _request(),
                reference_summary="Registered image reference.",
            )
        )
