class PCBIntelligenceError(Exception):
    """Base error for deterministic PCB intelligence operations."""


class PCBAnalysisError(PCBIntelligenceError):
    """Raised when a PCB requirement cannot be analyzed safely."""


class PCBKnowledgeError(PCBIntelligenceError):
    """Raised when PCB knowledge retrieval cannot be completed safely."""


class PCBRuleError(PCBIntelligenceError):
    """Raised when deterministic PCB rule evaluation fails."""


class PCBReviewError(PCBIntelligenceError):
    """Raised when a PCB review report cannot be produced safely."""


class PCBValidationError(PCBIntelligenceError):
    """Raised when a PCB review report cannot be validated safely."""


class PCBParseError(PCBIntelligenceError):
    """Raised when an EDA attachment cannot be parsed safely."""
