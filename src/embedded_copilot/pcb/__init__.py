"""Deterministic PCB design intelligence interfaces."""

from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.analyzer import PCBRequirementAnalyzer
from embedded_copilot.pcb.capability import (
    PCBCapability,
    PCBCapabilityDescriptor,
    register_pcb_foundation,
)
from embedded_copilot.pcb.exceptions import (
    PCBAnalysisError,
    PCBIntelligenceError,
    PCBKnowledgeError,
    PCBReviewError,
    PCBRuleError,
    PCBValidationError,
)
from embedded_copilot.pcb.models import (
    PCBIssue,
    PCBRequirement,
    PCBReviewReport,
    PCBRuleEvaluation,
    PCBValidationResult,
)
from embedded_copilot.pcb.reviewer import PCBReviewer
from embedded_copilot.pcb.rules import PCBRuleEngine
from embedded_copilot.pcb.validator import PCBValidator
from embedded_copilot.pcb.knowledge import PCBKnowledgeRetriever, PCBRuleDocument

__all__ = [
    "PCBAgent",
    "PCBAnalysisError",
    "PCBCapability",
    "PCBCapabilityDescriptor",
    "PCBIntelligenceError",
    "PCBIssue",
    "PCBKnowledgeError",
    "PCBKnowledgeRetriever",
    "PCBRequirement",
    "PCBRequirementAnalyzer",
    "PCBReviewer",
    "PCBReviewError",
    "PCBReviewReport",
    "PCBRuleError",
    "PCBRuleDocument",
    "PCBRuleEvaluation",
    "PCBRuleEngine",
    "PCBValidationError",
    "PCBValidationResult",
    "PCBValidator",
    "register_pcb_foundation",
]
