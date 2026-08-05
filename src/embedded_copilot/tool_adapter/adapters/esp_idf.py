from __future__ import annotations

from ..contracts import ToolExecutionRequest, ToolExecutionResult
from ..exceptions import ToolUnavailable
from ..executor import BuildExecutorPort, call_build_executor


class EspIdfToolAdapter:
    def __init__(self, executor: BuildExecutorPort | None = None) -> None:
        self._executor = executor

    def build(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        if self._executor is None:
            raise ToolUnavailable()
        try:
            return call_build_executor(self._executor, request)
        except Exception as error:
            raise ToolUnavailable() from error

    execute = build


ESPIdfToolAdapter = EspIdfToolAdapter
EspIdfAdapter = EspIdfToolAdapter
ESPIdfAdapter = EspIdfToolAdapter

__all__ = ["ESPIdfAdapter", "ESPIdfToolAdapter", "EspIdfToolAdapter"]
