from __future__ import annotations

from ..contracts import ToolExecutionRequest, ToolExecutionResult
from ..exceptions import FlashUnavailable
from ..executor import FlashExecutorPort, call_flash_executor


class OpenOcdToolAdapter:
    def __init__(self, executor: FlashExecutorPort | None = None) -> None:
        self._executor = executor

    def flash(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        if self._executor is None:
            raise FlashUnavailable()
        try:
            return call_flash_executor(self._executor, request)
        except Exception as error:
            raise FlashUnavailable() from error

    def reset(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        return self.flash(request)

    execute = flash


OpenOCDToolAdapter = OpenOcdToolAdapter
OpenOCDAdapter = OpenOcdToolAdapter

__all__ = ["OpenOCDAdapter", "OpenOcdToolAdapter", "OpenOCDToolAdapter"]
