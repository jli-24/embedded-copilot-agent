"""Sanitized Human Loop Runtime exceptions."""


class HumanLoopError(RuntimeError):
    """Base Human Loop error."""


class HumanLoopRejected(HumanLoopError):
    """Raised when a contract or lifecycle binding is rejected."""


class HumanReviewUnavailable(HumanLoopError):
    """Raised when proposal or human review delivery is unavailable."""


class FeedbackProjectionUnavailable(HumanLoopError):
    """Raised when structured feedback cannot be projected."""


class RevisionProposalUnavailable(HumanLoopError):
    """Raised when a revision proposal boundary is unavailable."""


class HumanLoopProgressUnavailable(HumanLoopError):
    """Raised when a progress event cannot be delivered safely."""
