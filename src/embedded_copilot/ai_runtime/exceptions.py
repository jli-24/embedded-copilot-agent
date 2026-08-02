"""Sanitized AI Runtime exceptions."""


class AIRuntimeError(Exception):
    """Base exception for AI Runtime boundary failures."""


class AIRequestRejected(AIRuntimeError):
    """Raised when a caller-owned request fails validation."""


class AIModelUnavailable(AIRuntimeError):
    """Raised when structured engineering reasoning is unavailable."""

