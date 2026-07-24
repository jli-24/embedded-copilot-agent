"""Deterministic PCB design intelligence interfaces."""

from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.adapters import attach_pcb_model
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
    PCBParseError,
    PCBReviewError,
    PCBRuleError,
    PCBValidationError,
)
from embedded_copilot.pcb.models import (
    PCBComponent,
    PCBIssue,
    PCBLayer,
    PCBNet,
    PCBNetNode,
    PCBNetType,
    PCBPin,
    PCBPosition,
    PCBRequirement,
    PCBReviewReport,
    PCBRuleEvaluation,
    PCBStructureEvidence,
    PCBTrack,
    PCBValidationResult,
    PCBVia,
    PCBZone,
    UnifiedPCBModel,
)
from embedded_copilot.pcb.parser import (
    KiCadPCBParser,
    PCBParser,
    PCBSourceResolver,
    RootedPCBSourceResolver,
)
from embedded_copilot.pcb.reviewer import PCBReviewer
from embedded_copilot.pcb.rules import PCBRuleEngine
from embedded_copilot.pcb.structure_rules import PCBStructureRuleEngine
from embedded_copilot.pcb.validator import PCBValidator
from embedded_copilot.pcb.knowledge import PCBKnowledgeRetriever, PCBRuleDocument

__all__ = [
    "PCBAgent",
    "PCBAnalysisError",
    "PCBCapability",
    "PCBCapabilityDescriptor",
    "PCBComponent",
    "PCBIntelligenceError",
    "PCBIssue",
    "KiCadPCBParser",
    "PCBKnowledgeError",
    "PCBKnowledgeRetriever",
    "PCBLayer",
    "PCBNet",
    "PCBNetNode",
    "PCBNetType",
    "PCBParseError",
    "PCBParser",
    "PCBPin",
    "PCBPosition",
    "PCBRequirement",
    "PCBRequirementAnalyzer",
    "PCBReviewer",
    "PCBReviewError",
    "PCBReviewReport",
    "PCBRuleError",
    "PCBRuleDocument",
    "PCBRuleEvaluation",
    "PCBRuleEngine",
    "PCBSourceResolver",
    "PCBStructureEvidence",
    "PCBStructureRuleEngine",
    "PCBTrack",
    "PCBValidationError",
    "PCBValidationResult",
    "PCBValidator",
    "PCBVia",
    "PCBZone",
    "RootedPCBSourceResolver",
    "UnifiedPCBModel",
    "attach_pcb_model",
    "register_pcb_foundation",
]
