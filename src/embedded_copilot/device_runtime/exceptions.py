class DeviceRuntimeError(RuntimeError):
    code = "DEVICE_RUNTIME_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class DeviceUnavailable(DeviceRuntimeError):
    code = "DEVICE_UNAVAILABLE"


class DeviceRequestRejected(DeviceRuntimeError):
    code = "DEVICE_REQUEST_REJECTED"
