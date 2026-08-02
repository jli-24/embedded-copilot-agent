"""Composition root for the framework-independent Agent Execution Runtime."""

from embedded_copilot.agent_execution.contracts import (
    AgentRegistryPort,
    ExecutionProgressSink,
    ExecutionVerificationPort,
)
from embedded_copilot.agent_execution.exceptions import AgentExecutionRejected
from embedded_copilot.agent_execution.facade import AgentExecutionRuntime
from embedded_copilot.agent_execution.runtime import _create_agent_execution_service


def create_agent_execution_runtime(
    *,
    agent_registry: AgentRegistryPort,
    progress_sink: ExecutionProgressSink,
    verification_port: ExecutionVerificationPort,
) -> AgentExecutionRuntime:
    """Create the runtime from caller-owned Protocol implementations."""
    if not isinstance(agent_registry, AgentRegistryPort):
        raise AgentExecutionRejected("agent registry is invalid")
    if not isinstance(progress_sink, ExecutionProgressSink):
        raise AgentExecutionRejected("execution progress sink is invalid")
    if not isinstance(verification_port, ExecutionVerificationPort):
        raise AgentExecutionRejected("execution verification port is invalid")
    return AgentExecutionRuntime._compose(
        _create_agent_execution_service(
            agent_registry=agent_registry,
            progress_sink=progress_sink,
            verification_port=verification_port,
        )
    )
