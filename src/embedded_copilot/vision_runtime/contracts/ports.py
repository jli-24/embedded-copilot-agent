from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.vision_runtime.contracts.models import (
    VisionRequest,
    VisionResponse,
)


@runtime_checkable
class VisionPort(Protocol):
    async def analyze(self, request: VisionRequest) -> VisionResponse: ...
