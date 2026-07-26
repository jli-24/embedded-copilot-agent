class VisionProviderUnavailable(RuntimeError):
    """A safe provider-unavailable failure for the API boundary."""


class VisionProviderTimeout(TimeoutError):
    """A safe request-scoped provider timeout."""


class VisionReferenceConflict(RuntimeError):
    """The registered reference cannot be used by the Vision Runtime."""
