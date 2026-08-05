class DigitalTwinError(RuntimeError):
    code = "DIGITAL_TWIN_UNAVAILABLE"


class DigitalTwinUnavailable(DigitalTwinError):
    code = "DIGITAL_TWIN_UNAVAILABLE"


class DigitalTwinRejected(DigitalTwinError):
    code = "DIGITAL_TWIN_REJECTED"


class DigitalTwinNotFound(DigitalTwinError):
    code = "DIGITAL_TWIN_NOT_FOUND"


__all__ = [
    "DigitalTwinError",
    "DigitalTwinNotFound",
    "DigitalTwinRejected",
    "DigitalTwinUnavailable",
]
