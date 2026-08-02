"""Sanitized Firmware Engineering exceptions."""


class FirmwareEngineeringError(RuntimeError):
    """Base error for the Firmware Engineering boundary."""


class FirmwareEngineeringRejected(FirmwareEngineeringError):
    """Raised when a typed request cannot be safely projected."""
