class EngineeringContextError(RuntimeError):
    """Base safe Engineering Context Runtime failure."""


class EngineeringContextReferenceNotFound(EngineeringContextError):
    """A requested context reference does not exist in the session."""


class EngineeringContextConflict(EngineeringContextError):
    """Context metadata conflicts with the requested aggregation."""


class EngineeringContextRejected(EngineeringContextError):
    """A referenced input cannot be represented as safe context."""


class EngineeringContextUnavailable(EngineeringContextError):
    """A required context source is unavailable."""


class EngineeringContextTimeout(EngineeringContextError):
    """Context composition exceeded a bounded source timeout."""
