"""Stateless Engineering Artifact orchestration."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_artifacts.exceptions import (
    EngineeringArtifactRejected,
)
from embedded_copilot.engineering_artifacts.integration.inputs import (
    EngineeringGenerationRequest,
    project_input,
)
from embedded_copilot.engineering_artifacts.models import EngineeringGenerationReport
from embedded_copilot.engineering_artifacts.projection import build_report


class _EngineeringArtifactAgent:
    def generate(
        self,
        request: EngineeringGenerationRequest,
    ) -> EngineeringGenerationReport:
        try:
            return build_report(project_input(request))
        except EngineeringArtifactRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise EngineeringArtifactRejected(
                "engineering artifact request rejected"
            ) from None
