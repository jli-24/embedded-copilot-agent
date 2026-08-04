class ModelRuntimeError(RuntimeError):
    code = "MODEL_RUNTIME_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ModelRequestRejected(ModelRuntimeError):
    code = "MODEL_REQUEST_REJECTED"


class ModelRuntimeUnavailable(ModelRuntimeError):
    code = "MODEL_UNAVAILABLE"
