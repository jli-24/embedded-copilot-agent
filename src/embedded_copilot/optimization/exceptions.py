"""Sanitized Optimization Runtime exceptions."""


class OptimizationError(Exception):
    """Base class for optimization boundary failures."""


class OptimizationRejected(OptimizationError):
    """A typed contract, binding, or replay was rejected."""


class OptimizationUnavailable(OptimizationError):
    """A required caller-owned optimization dependency is unavailable."""


class OptimizationProgressUnavailable(OptimizationError):
    """A content-free progress event could not be delivered."""
