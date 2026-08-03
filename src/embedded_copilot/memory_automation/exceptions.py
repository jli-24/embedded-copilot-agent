class MemoryAutomationError(RuntimeError):
    """Base error for deterministic memory projection failures."""


class MemoryProjectionRejected(MemoryAutomationError):
    def __init__(self) -> None:
        super().__init__("MEMORY_PROJECTION_REJECTED")


class MemoryApprovalRejected(MemoryAutomationError):
    def __init__(self) -> None:
        super().__init__("MEMORY_APPROVAL_REJECTED")
