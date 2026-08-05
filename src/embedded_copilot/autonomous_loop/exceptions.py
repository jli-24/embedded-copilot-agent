class AutonomousLoopError(RuntimeError):
    code = "LOOP_REJECTED"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class LoopNotFound(AutonomousLoopError):
    code = "LOOP_NOT_FOUND"


class InvalidTransition(AutonomousLoopError):
    code = "INVALID_TRANSITION"


class ActionApprovalRequired(AutonomousLoopError):
    code = "ACTION_APPROVAL_REQUIRED"


class LoopRejected(AutonomousLoopError):
    code = "LOOP_REJECTED"
