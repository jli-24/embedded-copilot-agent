"""Composition root for deterministic Engineering Artifacts."""

from embedded_copilot.engineering_artifacts.facade import EngineeringArtifactRuntime
from embedded_copilot.engineering_artifacts.runtime import _EngineeringArtifactAgent


def create_engineering_artifact_runtime() -> EngineeringArtifactRuntime:
    return EngineeringArtifactRuntime._compose(_EngineeringArtifactAgent())
