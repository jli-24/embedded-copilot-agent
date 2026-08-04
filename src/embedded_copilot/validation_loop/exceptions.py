class ValidationLoopError(RuntimeError):
    code = "VALIDATION_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ValidationUnavailable(ValidationLoopError):
    code = "VALIDATION_UNAVAILABLE"


class ValidationRejected(ValidationLoopError):
    code = "VALIDATION_SNAPSHOT_REJECTED"
