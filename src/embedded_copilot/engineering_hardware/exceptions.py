"""Sanitized Hardware Engineering failures."""


class HardwareEngineeringError(RuntimeError):
    """Base class for Hardware Engineering failures."""


class HardwareEngineeringRejected(HardwareEngineeringError):
    """Raised when a request or derived proposal fails closed."""
