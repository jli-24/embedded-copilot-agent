class ApprovalGateError(RuntimeError):
    code = "APPROVAL_GATE_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ActionApprovalRequired(ApprovalGateError):
    code = "ACTION_APPROVAL_REQUIRED"


class ApprovalRejected(ApprovalGateError):
    code = "LOOP_REJECTED"


class ApprovalExpired(ApprovalGateError):
    code = "APPROVAL_EXPIRED"
