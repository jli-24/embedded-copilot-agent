from __future__ import annotations

from typing import Protocol

from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.model_runtime.health.models import ModelStatusResponse


class StatusPort(Protocol):
    async def status(self) -> ModelStatusResponse: ...


class ModelRuntime:
    __slots__ = ("_reasoning", "_status")

    def __init__(self, reasoning: ReasoningPort, status: StatusPort) -> None:
        self._reasoning = reasoning
        self._status = status

    def reasoning_port(self) -> ReasoningPort:
        return self._reasoning

    def status_port(self) -> StatusPort:
        return self._status
