"""Sanitized Hardware Validation errors."""


class HardwareValidationError(Exception):
    """Base error for the Hardware Validation boundary."""


class HardwareValidationRejected(HardwareValidationError):
    """Raised when caller-owned typed input fails closed validation."""
