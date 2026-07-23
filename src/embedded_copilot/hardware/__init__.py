"""Deterministic hardware design intelligence interfaces."""

from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.analyzer import HardwareRequirementAnalyzer
from embedded_copilot.hardware.capability import (
    HardwareCapability,
    HardwareCapabilityDescriptor,
    register_hardware_foundation,
)
from embedded_copilot.hardware.exceptions import (
    HardwareAnalysisError,
    HardwareIntelligenceError,
    HardwareKnowledgeError,
    HardwarePlanningError,
    HardwareValidationError,
)
from embedded_copilot.hardware.knowledge import (
    HardwareDocument,
    HardwareKnowledgeRetriever,
)
from embedded_copilot.hardware.models import (
    HardwareComponent,
    HardwarePlan,
    HardwareRequirement,
    HardwareValidationResult,
)
from embedded_copilot.hardware.planner import HardwarePlanner
from embedded_copilot.hardware.validator import HardwareValidator

__all__ = [
    "HardwareAgent",
    "HardwareAnalysisError",
    "HardwareCapability",
    "HardwareCapabilityDescriptor",
    "HardwareComponent",
    "HardwareDocument",
    "HardwareIntelligenceError",
    "HardwareKnowledgeError",
    "HardwareKnowledgeRetriever",
    "HardwarePlan",
    "HardwarePlanningError",
    "HardwareRequirement",
    "HardwareRequirementAnalyzer",
    "HardwarePlanner",
    "HardwareValidationResult",
    "HardwareValidationError",
    "HardwareValidator",
    "register_hardware_foundation",
]
