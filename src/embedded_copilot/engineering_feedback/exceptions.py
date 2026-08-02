"""Sanitized Engineering Feedback exceptions."""


class EngineeringFeedbackError(RuntimeError):
    """Base error for the Engineering Feedback boundary."""


class EngineeringFeedbackRejected(EngineeringFeedbackError):
    """Raised when a typed request or source binding is invalid."""
