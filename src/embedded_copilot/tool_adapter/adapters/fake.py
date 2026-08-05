from __future__ import annotations

from ..contracts import (
    ToolCapabilitySnapshot,
    ToolCapabilityStatus,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)


class FakeToolAdapter:
    """Deterministic adapter for offline tests."""

    def get_snapshot(self, project_id: str) -> ToolCapabilitySnapshot:
        return ToolCapabilitySnapshot.create(
            tool_name="FAKE",
            version="1",
            capabilities=("build", "flash", "debug", "observe"),
            status=ToolCapabilityStatus.AVAILABLE,
        )

    def build(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        return ToolExecutionResult.create(
            status=ToolExecutionStatus.SUCCESS,
            tool_type=request.tool_type,
            operation="build",
            artifact_reference=request.artifact_reference,
            summary="Build completed as an approved projection.",
        )

    def flash(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        return ToolExecutionResult.create(
            status=ToolExecutionStatus.SUCCESS,
            tool_type=request.tool_type,
            operation="flash",
            artifact_reference=request.artifact_reference,
            summary="Flash completed through the approved adapter boundary.",
        )

    def get_device(self, project_id: str) -> object:
        return None

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        if request.operation == "flash":
            return self.flash(request)
        return self.build(request)


__all__ = ["FakeToolAdapter"]
