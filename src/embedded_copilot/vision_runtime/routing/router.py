from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.vision_runtime.contracts import VisionRequest
from embedded_copilot.vision_runtime.providers import (
    ProviderVisionResponse,
    VisionCapability,
    VisionProvider,
    VisionProviderUnavailable,
)

_UNAVAILABLE_MESSAGE = "vision provider is unavailable"


@dataclass(frozen=True, slots=True)
class VisionProviderRegistry:
    _providers: tuple[VisionProvider, ...]

    def matching(
        self,
        capability: VisionCapability,
    ) -> tuple[VisionProvider, ...]:
        return tuple(
            provider
            for provider in self._providers
            if capability in provider.supported_capabilities
        )


@dataclass(frozen=True, slots=True)
class VisionRouter:
    _registry: VisionProviderRegistry

    async def analyze(
        self,
        request: VisionRequest,
        *,
        reference_summary: str,
    ) -> ProviderVisionResponse:
        providers = self._registry.matching(VisionCapability.VISION)
        if not providers:
            raise VisionProviderUnavailable(_UNAVAILABLE_MESSAGE)
        selected = providers[0]
        return await selected.analyze(
            request,
            reference_summary=reference_summary,
        )
