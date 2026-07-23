"""Safe exception hierarchy for Foundation Debug Intelligence."""


class DebugIntelligenceError(Exception):
    """Base error for deterministic Debug processing."""


class DebugAnalysisError(DebugIntelligenceError):
    """Raised when debug input or findings cannot be analyzed safely."""


class DebugKnowledgeError(DebugIntelligenceError):
    """Raised when injected debug knowledge cannot be retrieved safely."""


class DebugPlanningError(DebugIntelligenceError):
    """Raised when a deterministic debug plan cannot be created."""


class DebugValidationError(DebugIntelligenceError):
    """Raised when a debug report cannot be validated safely."""
