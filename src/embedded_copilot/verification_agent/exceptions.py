class VerificationAgentError(RuntimeError):
    __slots__ = ()


class VerificationRequestRejected(VerificationAgentError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("verification request rejected")


class VerificationCheckerUnavailable(VerificationAgentError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("verification checker unavailable")


class VerificationAuditUnavailable(VerificationAgentError):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__("verification audit unavailable")
