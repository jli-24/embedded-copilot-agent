from __future__ import annotations

from ..contracts import ToolExecutionRequest, ToolExecutionResult
from ..exceptions import FlashUnavailable
from ..executor import JLinkExecutorPort, call_flash_executor


class JLinkToolAdapter:
    def __init__(self, executor: JLinkExecutorPort | None = None) -> None:
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


JLinkAdapter = JLinkToolAdapter

__all__ = ["JLinkAdapter", "JLinkToolAdapter"]
