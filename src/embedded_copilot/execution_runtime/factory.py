"""Composition factory for the Execution Integration Runtime."""

from __future__ import annotations

from embedded_copilot.execution_runtime.contracts import (
    ExecutionExecutorRegistryPort,
    ExecutionProgressSink,
    ExecutionVerificationPort,
)
from embedded_copilot.execution_runtime.exceptions import ExecutionRejected
from embedded_copilot.execution_runtime.executor.service import _ExecutionService
from embedded_copilot.execution_runtime.facade import ExecutionRuntime


def create_execution_runtime(
    *,
    executor_registry: ExecutionExecutorRegistryPort,
    verification_port: ExecutionVerificationPort,
    progress_sink: ExecutionProgressSink,
) -> ExecutionRuntime:
    """Compose a process-local controlled execution boundary."""
    boundaries = (
        (executor_registry, ExecutionExecutorRegistryPort),
        (verification_port, ExecutionVerificationPort),
        (progress_sink, ExecutionProgressSink),
    )
    for value, contract in boundaries:
        try:
            valid = isinstance(value, contract)
        except Exception:
            raise ExecutionRejected(
                "execution runtime configuration was rejected"
            ) from None
        if not valid:
            raise ExecutionRejected("execution runtime configuration was rejected")
    return ExecutionRuntime._compose(
        _ExecutionService(
            executor_registry=executor_registry,
            verification_port=verification_port,
            progress_sink=progress_sink,
        )
    )
