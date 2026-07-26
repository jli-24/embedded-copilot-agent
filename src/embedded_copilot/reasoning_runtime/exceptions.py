class ReasoningError(RuntimeError):
    """Base safe Reasoning Runtime failure."""


class ReasoningContextNotFound(ReasoningError):
    """A referenced engineering context input does not exist."""


class ReasoningContextConflict(ReasoningError):
    """The supplied context identity conflicts with its safe snapshot."""


class ReasoningRequestRejected(ReasoningError):
    """The reasoning request cannot be represented safely."""


class ReasoningRuntimeUnavailable(ReasoningError):
    """Reasoning analysis is unavailable."""


class ReasoningAnalysisTimeout(ReasoningError):
    """Reasoning context preparation exceeded its time bound."""
