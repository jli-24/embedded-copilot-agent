from __future__ import annotations

from embedded_copilot.toolchain.contracts import (
    BuildPort,
    BuildResult,
    BuildStatus,
    ToolchainArtifactReference,
)


class FakeBuildPort(BuildPort):
    def build(self, workspace_reference: str) -> BuildResult:
        return BuildResult.create(
            status=BuildStatus.SUCCESS,
            artifact_reference=ToolchainArtifactReference(
                reference_id=f"build-{workspace_reference}", artifact_type="FIRMWARE"
            ),
            summary="Deterministic build result for review.",
        )


__all__ = ["FakeBuildPort"]
