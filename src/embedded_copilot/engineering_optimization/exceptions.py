"""Redacted Engineering Optimization exceptions."""


class EngineeringOptimizationError(Exception):
    """Base exception for the Engineering Optimization boundary."""


class EngineeringOptimizationRejected(EngineeringOptimizationError):
    """Raised when an optimization request fails closed."""


__all__ = ("EngineeringOptimizationError", "EngineeringOptimizationRejected")
