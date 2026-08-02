"""Sanitized Engineering Execution exceptions."""


class EngineeringExecutionError(Exception):
    """Base class for safe Engineering Execution failures."""


class EngineeringExecutionRejected(EngineeringExecutionError):
    """Raised when caller-owned execution bindings are invalid."""
