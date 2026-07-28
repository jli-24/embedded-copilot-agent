class TelemetryRuntimeError(RuntimeError):
    __slots__ = ()


class TelemetrySourceUnavailable(TelemetryRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("telemetry source unavailable")


class TelemetryDataRejected(TelemetryRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("telemetry data rejected")


class TelemetryObservationTimeout(TelemetryRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("telemetry observation timed out")


class TelemetryAuditUnavailable(TelemetryRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("telemetry audit unavailable")
