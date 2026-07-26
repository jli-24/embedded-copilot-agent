from __future__ import annotations

from embedded_copilot.context_runtime.contracts import EngineeringContextPort


class EngineeringContextRuntime:
    __slots__ = ("_context_port",)

    def __init__(self, context_port: EngineeringContextPort) -> None:
        self._context_port = context_port

    @classmethod
    def _compose(
        cls,
        context_port: EngineeringContextPort,
    ) -> "EngineeringContextRuntime":
        if not isinstance(context_port, EngineeringContextPort):
            raise TypeError("context port is invalid")
        return cls(context_port)

    def context_port(self) -> EngineeringContextPort:
        return self._context_port
