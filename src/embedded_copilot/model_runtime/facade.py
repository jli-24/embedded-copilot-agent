from __future__ import annotations

from embedded_copilot.conversation.reasoning import ReasoningPort


class ModelRuntime:
    __slots__ = ("_reasoning",)

    def __init__(self, reasoning: ReasoningPort) -> None:
        self._reasoning = reasoning

    def reasoning_port(self) -> ReasoningPort:
        return self._reasoning
