from __future__ import annotations


class EngineeringContextError(Exception):
    """Base error for the read-only context boundary."""


class EngineeringContextRejected(EngineeringContextError):
    """The supplied projection violates the context contract."""


class EngineeringContextUnavailable(EngineeringContextError):
    """A required read-only projection is unavailable."""


__all__ = (
    "EngineeringContextError",
    "EngineeringContextRejected",
    "EngineeringContextUnavailable",
)
