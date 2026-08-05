class HardwareDesignError(RuntimeError):
    code = "HARDWARE_DESIGN_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class KiCadUnavailable(HardwareDesignError):
    code = "KICAD_UNAVAILABLE"


class DesignRejected(HardwareDesignError):
    code = "DESIGN_REJECTED"
