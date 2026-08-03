from __future__ import annotations


class ReasoningError(Exception):
    """Base error for the read-only reasoning layer."""


class ReasoningRequestRejected(ReasoningError):
    """The supplied typed projections or bindings were invalid."""


class ReasoningRuntimeUnavailable(ReasoningError):
    """No reasoning adapter is available for the request."""
