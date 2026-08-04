class GenerationError(Exception):
    """Base error for the deterministic generation boundary."""


class GenerationRequestRejected(GenerationError):
    """The typed generation input failed validation or identity binding."""


class GenerationRuntimeUnavailable(GenerationError):
    """A generation adapter is not configured or cannot provide a projection."""
