"""Sanitized Engineering Intelligence failures."""


class EngineeringIntelligenceError(RuntimeError):
    """Base class for Engineering Intelligence failures."""


class EngineeringIntelligenceRejected(EngineeringIntelligenceError):
    """Raised when a contract or derived projection fails closed."""


class EngineeringKnowledgeUnavailable(EngineeringIntelligenceError):
    """Raised when an injected knowledge source is unavailable."""
