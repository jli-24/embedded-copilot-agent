"""Sanitized failures for the Engineering Interface boundary."""


class EngineeringInterfaceError(RuntimeError):
    """Base class for interface boundary failures."""


class EngineeringInterfaceRejected(EngineeringInterfaceError):
    """Raised when an interface request or projection fails validation."""


class EngineeringWorkflowUnavailable(EngineeringInterfaceError):
    """Raised when workflow preparation cannot produce a safe projection."""
