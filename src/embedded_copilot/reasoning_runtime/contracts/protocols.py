from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.reasoning_runtime.contracts.models import (
    ReasoningRequest,
    ReasoningResponse,
)


@runtime_checkable
class ReasoningPort(Protocol):
    async def analyze(self, request: ReasoningRequest) -> ReasoningResponse: ...
