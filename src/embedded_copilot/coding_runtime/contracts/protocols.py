from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.coding_runtime.contracts.models import (
    BuildAnalysisRequest,
    BuildAnalysisResponse,
    ChangeReview,
    DiffReviewRequest,
    HardwareSoftwareFusionRequest,
    HardwareSoftwareFusionResponse,
    ProjectAnalysisRequest,
    ProjectAnalysisResponse,
)


@runtime_checkable
class CodingIntelligencePort(Protocol):
    def analyze_project(
        self, request: ProjectAnalysisRequest
    ) -> ProjectAnalysisResponse: ...

    def analyze_build(self, request: BuildAnalysisRequest) -> BuildAnalysisResponse: ...

    def review_diff(self, request: DiffReviewRequest) -> ChangeReview: ...

    def analyze_hardware_software(
        self, request: HardwareSoftwareFusionRequest
    ) -> HardwareSoftwareFusionResponse: ...


class CodeParser(Protocol):
    def parse(self, path: str, content: str): ...


class ProjectAnalyzer(Protocol):
    def analyze(self, files): ...


class BuildAnalyzer(Protocol):
    def analyze(self, request: BuildAnalysisRequest) -> BuildAnalysisResponse: ...


class DiffAnalyzer(Protocol):
    def analyze(self, request: DiffReviewRequest) -> ChangeReview: ...


class DependencyAnalyzer(Protocol):
    def dependencies(self, parsed): ...


class HardwareSoftwareAnalyzer(Protocol):
    def analyze(
        self, request: HardwareSoftwareFusionRequest
    ) -> HardwareSoftwareFusionResponse: ...
