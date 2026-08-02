"""Narrow public facade for Agent Execution Runtime composition."""

from __future__ import annotations

from embedded_copilot.agent_execution.contracts import AgentExecutionPort


class AgentExecutionRuntime:
    """Expose only the stable AgentExecutionPort."""

    __slots__ = ("__execution_port",)

    def __init__(self, execution_port: AgentExecutionPort) -> None:
        raise TypeError(
            "AgentExecutionRuntime must be created by the composition factory"
        )

    @classmethod
    def _compose(cls, execution_port: AgentExecutionPort) -> AgentExecutionRuntime:
        runtime = object.__new__(cls)
        object.__setattr__(
            runtime, "_AgentExecutionRuntime__execution_port", execution_port
        )
        return runtime

    def execution_port(self) -> AgentExecutionPort:
        return self.__execution_port
