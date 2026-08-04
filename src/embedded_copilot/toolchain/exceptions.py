class ToolchainError(RuntimeError):
    code = "TOOLCHAIN_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ToolchainUnavailable(ToolchainError):
    code = "TOOLCHAIN_UNAVAILABLE"


class BuildFailed(ToolchainError):
    code = "BUILD_FAILED"


class FlashUnavailable(ToolchainError):
    code = "FLASH_UNAVAILABLE"


class FlashApprovalRequired(ToolchainError):
    code = "FLASH_APPROVAL_REQUIRED"


class FlashCapabilityRequired(ToolchainError):
    code = "FLASH_CAPABILITY_REQUIRED"


class FlashFailed(ToolchainError):
    code = "FLASH_FAILED"


class RunUnavailable(ToolchainError):
    code = "RUN_UNAVAILABLE"
