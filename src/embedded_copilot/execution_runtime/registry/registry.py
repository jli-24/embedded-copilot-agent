"""Private immutable executor binding."""

from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.execution_runtime.contracts import ExecutionExecutorPort
from embedded_copilot.execution_runtime.models import ExecutionExecutorMetadata


@dataclass(frozen=True, slots=True)
class _ExecutionExecutorBinding:
    metadata: ExecutionExecutorMetadata
    executor: ExecutionExecutorPort


__all__: tuple[str, ...] = ()
