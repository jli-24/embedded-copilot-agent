from __future__ import annotations

from embedded_copilot.tool_runtime.ports import ToolExecutionPort


class ToolRuntime:
    __slots__ = ("_tool_port",)

    def __init__(self, tool_port: ToolExecutionPort) -> None:
        raise TypeError("ToolRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, tool_port: ToolExecutionPort) -> "ToolRuntime":
        if not isinstance(tool_port, ToolExecutionPort):
            raise TypeError("tool port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_tool_port", tool_port)
        return runtime

    def tool_port(self) -> ToolExecutionPort:
        return self._tool_port
