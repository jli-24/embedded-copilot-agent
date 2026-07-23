class FirmwareIntelligenceError(Exception):
    """Base error for deterministic firmware intelligence operations."""


class FirmwareKnowledgeError(FirmwareIntelligenceError):
    """Raised when firmware knowledge cannot be loaded or normalized."""


class FirmwareAnalysisError(FirmwareIntelligenceError):
    """Raised when a firmware requirement cannot be analyzed safely."""


class FirmwarePlanningError(FirmwareIntelligenceError):
    """Raised when a deterministic firmware plan cannot be created."""


class FirmwareGenerationError(FirmwareIntelligenceError):
    """Raised when a firmware request cannot produce mock generated code."""
