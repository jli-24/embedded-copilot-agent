from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.conversation.reasoning import (
    ReasoningPort as ConversationReasoningPort,
)
from embedded_copilot.model_runtime.health.models import ModelStatusResponse
from embedded_copilot.reasoning_runtime import (
    ReasoningPort as IntelligenceReasoningPort,
)


@runtime_checkable
class StatusPort(Protocol):
    async def status(self) -> ModelStatusResponse: ...


@runtime_checkable
class PresentationEnhancer(Protocol):
    def wrap(self, base: IntelligenceReasoningPort) -> IntelligenceReasoningPort: ...


class ModelRuntime:
    __slots__ = ("_presentation", "_reasoning", "_status")

    def __init__(
        self,
        reasoning: ConversationReasoningPort,
        status: StatusPort,
        presentation: PresentationEnhancer,
    ) -> None:
        raise TypeError("ModelRuntime must be created by the composition factory")

    @classmethod
    def _compose(
        cls,
        reasoning: ConversationReasoningPort,
        status: StatusPort,
        presentation: PresentationEnhancer,
    ) -> "ModelRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_reasoning", reasoning)
        object.__setattr__(runtime, "_status", status)
        object.__setattr__(runtime, "_presentation", presentation)
        return runtime

    def reasoning_port(self) -> ConversationReasoningPort:
        return self._reasoning

    def status_port(self) -> StatusPort:
        return self._status

    def enhance_reasoning_port(
        self,
        base: IntelligenceReasoningPort,
    ) -> IntelligenceReasoningPort:
        return self._presentation.wrap(base)
