"""Public facade for the Execution Integration Runtime."""

from __future__ import annotations

from embedded_copilot.execution_runtime.contracts import ExecutionPort


class ExecutionRuntime:
    """Expose only the stable controlled-execution Protocol."""

    __slots__ = ("_port",)

    def __init__(self, port: ExecutionPort) -> None:
        raise TypeError("ExecutionRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, port: ExecutionPort) -> ExecutionRuntime:
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_port", port)
        return runtime

    def execution_port(self) -> ExecutionPort:
        return self._port
