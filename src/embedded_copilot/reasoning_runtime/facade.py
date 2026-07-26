from __future__ import annotations

from embedded_copilot.reasoning_runtime.contracts import ReasoningPort


class ReasoningRuntime:
    __slots__ = ("_reasoning_port",)

    def __init__(self, reasoning_port: ReasoningPort) -> None:
        raise TypeError("ReasoningRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, reasoning_port: ReasoningPort) -> "ReasoningRuntime":
        if not isinstance(reasoning_port, ReasoningPort):
            raise TypeError("reasoning port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_reasoning_port", reasoning_port)
        return runtime

    def reasoning_port(self) -> ReasoningPort:
        return self._reasoning_port
