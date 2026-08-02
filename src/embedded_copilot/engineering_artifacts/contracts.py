"""Public Protocol boundary for Engineering Artifacts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_artifacts.integration.inputs import (
    EngineeringGenerationRequest,
)
from embedded_copilot.engineering_artifacts.models import EngineeringGenerationReport


@runtime_checkable
class EngineeringArtifactPort(Protocol):
    def generate(
        self,
        request: EngineeringGenerationRequest,
    ) -> EngineeringGenerationReport: ...
