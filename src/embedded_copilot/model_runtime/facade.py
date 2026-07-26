from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.model_runtime.health.models import ModelStatusResponse


@runtime_checkable
class StatusPort(Protocol):
    async def status(self) -> ModelStatusResponse: ...


class ModelRuntime:
    __slots__ = ("_reasoning", "_status")

    def __init__(self, reasoning: ReasoningPort, status: StatusPort) -> None:
        raise TypeError("ModelRuntime must be created by the composition factory")

    @classmethod
    def _compose(
        cls,
        reasoning: ReasoningPort,
        status: StatusPort,
    ) -> "ModelRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_reasoning", reasoning)
        object.__setattr__(runtime, "_status", status)
        return runtime

    def reasoning_port(self) -> ReasoningPort:
        return self._reasoning

    def status_port(self) -> StatusPort:
        return self._status
