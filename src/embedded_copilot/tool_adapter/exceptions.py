from __future__ import annotations


class ToolAdapterError(RuntimeError):
    """Base error with no provider or environment details."""

    code = "TOOL_ADAPTER_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ToolUnavailable(ToolAdapterError):
    code = "TOOL_UNAVAILABLE"


class BuildApprovalRequired(ToolAdapterError):
    code = "BUILD_APPROVAL_REQUIRED"


class FlashApprovalRequired(ToolAdapterError):
    code = "FLASH_APPROVAL_REQUIRED"


class FlashUnavailable(ToolAdapterError):
    code = "FLASH_UNAVAILABLE"


class FlashFailed(ToolAdapterError):
    code = "FLASH_FAILED"


class ObservationUnavailable(ToolAdapterError):
    code = "OBSERVATION_UNAVAILABLE"


class ToolExecutionRejected(ToolAdapterError):
    code = "TOOL_EXECUTION_REJECTED"
