from __future__ import annotations

import copy

from .contracts import (
    ToolBuildPort,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolFlashPort,
    validate_execution_request,
    validate_execution_result,
)
from .exceptions import (
    BuildApprovalRequired,
    FlashApprovalRequired,
    FlashFailed,
    FlashUnavailable,
    ToolUnavailable,
)


class ToolAdapterService:
    __slots__ = ("_build", "_flash")

    def __init__(
        self,
        *,
        build_port: ToolBuildPort | None = None,
        flash_port: ToolFlashPort | None = None,
    ) -> None:
        self._build = build_port
        self._flash = flash_port

    def build(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        checked = validate_execution_request(request)
        if checked.approval_reference is None:
            raise BuildApprovalRequired()
        if self._build is None:
            raise ToolUnavailable()
        try:
            return validate_execution_result(self._build.build(copy.deepcopy(checked)))
        except (BuildApprovalRequired, ToolUnavailable):
            raise
        except Exception as error:
            raise ToolUnavailable() from error

    def flash(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        checked = validate_execution_request(request)
        if checked.approval_reference is None:
            raise FlashApprovalRequired()
        if self._flash is None:
            raise FlashUnavailable()
        try:
            return validate_execution_result(self._flash.flash(copy.deepcopy(checked)))
        except (FlashApprovalRequired, FlashUnavailable, FlashFailed):
            raise
        except Exception as error:
            raise FlashFailed() from error

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        checked = validate_execution_request(request)
        if checked.operation == "build":
            return self.build(checked)
        if checked.operation == "flash":
            return self.flash(checked)
        raise ToolUnavailable()
