"""Public Protocol boundaries for Engineering Intelligence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_intelligence.models import (
    EngineeringContextRequest,
    EngineeringContextSnapshot,
    EngineeringIntelligenceRequest,
    EngineeringIntelligenceSnapshot,
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
    EngineeringRequirementRequest,
    WebResearchRequest,
    WebResearchResult,
)


@runtime_checkable
class WebResearchPort(Protocol):
    def research(self, request: WebResearchRequest) -> WebResearchResult: ...


@runtime_checkable
class EngineeringIntelligencePort(Protocol):
    def analyze_requirement(
        self,
        request: EngineeringRequirementRequest,
    ) -> EngineeringRequirementDocument: ...

    def create_plan(
        self,
        requirement: EngineeringRequirementDocument,
    ) -> EngineeringProjectPlan: ...

    def build_context(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextSnapshot: ...

    def prepare_project(
        self,
        request: EngineeringIntelligenceRequest,
    ) -> EngineeringIntelligenceSnapshot: ...
