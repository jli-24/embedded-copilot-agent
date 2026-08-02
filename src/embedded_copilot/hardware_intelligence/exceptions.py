"""Sanitized exceptions for the Hardware Intelligence Runtime."""


class HardwareIntelligenceError(Exception):
    """Base class for hardware-intelligence boundary failures."""


class HardwareIntelligenceUnavailable(HardwareIntelligenceError):
    """A required caller-owned projection provider is unavailable."""


class HardwareIntelligenceRejected(HardwareIntelligenceError):
    """An invalid typed input, binding, or projection was rejected."""


class HardwareObservationRejected(HardwareIntelligenceError):
    """A structured hardware observation failed validation."""


class HardwareValidationUnavailable(HardwareIntelligenceError):
    """The hardware validation projection could not be produced."""


class HardwareProgressUnavailable(HardwareIntelligenceError):
    """A required content-free progress event could not be delivered."""
