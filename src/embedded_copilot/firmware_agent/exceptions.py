"""Sanitized Firmware Agent exceptions."""


class FirmwareAgentError(Exception):
    """Base error for the Firmware Agent boundary."""


class FirmwareGenerationRejected(FirmwareAgentError):
    """Raised when a firmware proposal cannot be safely projected."""
