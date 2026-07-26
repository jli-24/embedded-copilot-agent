from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.vision_runtime.contracts import VisionRequest
from embedded_copilot.vision_runtime.providers.base import (
    ProviderVisionResponse,
    VisionCapability,
    VisionProviderUnavailable,
)

_UNAVAILABLE_MESSAGE = "vision provider is unavailable"


@dataclass(frozen=True, slots=True)
class UnavailableVisionProvider:
    provider_id = "unavailable"
    supported_capabilities = (VisionCapability.VISION,)

    async def analyze(
        self,
        request: VisionRequest,
        *,
        reference_summary: str,
    ) -> ProviderVisionResponse:
        raise VisionProviderUnavailable(_UNAVAILABLE_MESSAGE)
