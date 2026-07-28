class DebugRuntimeError(RuntimeError):
    __slots__ = ()


class DebugSourceUnavailable(DebugRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("debug source unavailable")


class DebugObservationRejected(DebugRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("debug observation rejected")


class DebugObservationTimeout(DebugRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("debug observation timed out")


class DebugAuditUnavailable(DebugRuntimeError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("debug audit unavailable")
