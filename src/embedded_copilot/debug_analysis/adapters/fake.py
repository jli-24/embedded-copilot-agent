from __future__ import annotations

from ..contracts import (
    DebugAnalysisPort,
    DebugAnalysisSnapshot,
    DebugAnalyzerPort,
    DebugCategory,
    DebugFinding,
    DebugInputSnapshot,
    DebugSeverity,
    DebugSourceType,
    DebugStatus,
)


class FakeDebugAnalyzer(DebugAnalyzerPort):
    def analyze(self, value: DebugInputSnapshot) -> DebugAnalysisSnapshot:
        finding = DebugFinding.create(
            finding_id=f"finding:{value.project_id}:1",
            project_id=value.project_id,
            source_type=DebugSourceType.VALIDATION,
            category=DebugCategory.UNKNOWN,
            severity=DebugSeverity.MEDIUM,
            summary="Validation failure requires structured engineering review.",
            evidence_reference=value.evidence_reference,
            status=DebugStatus.PROJECTED,
        )
        return DebugAnalysisSnapshot.create(
            project_id=value.project_id,
            failure_reference=value.failure_reference,
            findings=(finding,),
        )


class FakeDebugAnalysisPort(DebugAnalysisPort):
    def get_snapshot(self, project_id: str) -> DebugAnalysisSnapshot:
        value = DebugInputSnapshot.create(
            project_id=project_id,
            failure_reference=f"failure:{project_id}",
            failure_type="VALIDATION",
            safe_summary="Validation failure requires analysis.",
            evidence_reference=f"evidence:{project_id}",
        )
        return FakeDebugAnalyzer().analyze(value)


__all__ = ["FakeDebugAnalysisPort", "FakeDebugAnalyzer"]
