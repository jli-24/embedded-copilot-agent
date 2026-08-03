"""Sanitized build execution errors."""


class BuildExecutionError(Exception):
    """Base error for the controlled build boundary."""


class BuildExecutionRejected(BuildExecutionError):
    """Raised when a typed build request fails validation."""
