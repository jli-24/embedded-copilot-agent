class HardwareIntelligenceError(Exception):
    """Base error for deterministic hardware intelligence operations."""


class HardwareAnalysisError(HardwareIntelligenceError):
    """Raised when a hardware requirement cannot be analyzed safely."""


class HardwareKnowledgeError(HardwareIntelligenceError):
    """Raised when hardware knowledge retrieval cannot be completed safely."""


class HardwarePlanningError(HardwareIntelligenceError):
    """Raised when a deterministic hardware plan cannot be created."""


class HardwareValidationError(HardwareIntelligenceError):
    """Raised when a hardware plan cannot be validated safely."""
