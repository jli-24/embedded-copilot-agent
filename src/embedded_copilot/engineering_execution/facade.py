"""Narrow facade for the Engineering Execution Layer."""

from __future__ import annotations

from embedded_copilot.engineering_execution.contracts import EngineeringExecutionPort


class EngineeringExecutionRuntime:
    __slots__ = ("__port",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_engineering_execution_runtime")

    @classmethod
    def _compose(cls, port: EngineeringExecutionPort) -> EngineeringExecutionRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def engineering_execution_port(self) -> EngineeringExecutionPort:
        return self.__port
