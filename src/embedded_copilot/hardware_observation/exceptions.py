class ObservationError(RuntimeError):
    code = "OBSERVATION_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ObservationUnavailable(ObservationError):
    code = "OBSERVATION_UNAVAILABLE"


class ObservationRejected(ObservationError):
    code = "OBSERVATION_REJECTED"
