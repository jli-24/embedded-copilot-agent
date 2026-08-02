"""Composition root for deterministic Engineering Intelligence."""

from embedded_copilot.engineering_intelligence.facade import (
    EngineeringIntelligenceRuntime,
)
from embedded_copilot.engineering_intelligence.runtime import (
    _EngineeringIntelligenceService,
)


def create_engineering_intelligence_runtime() -> EngineeringIntelligenceRuntime:
    return EngineeringIntelligenceRuntime._compose(_EngineeringIntelligenceService())
