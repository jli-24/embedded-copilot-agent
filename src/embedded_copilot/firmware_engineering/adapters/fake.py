from __future__ import annotations

from ..contracts import (
    BuildConfigurationProjection,
    FirmwareBuildPort,
    FirmwareBuildRequest,
    FirmwareBuildResult,
    FirmwareBuildStatus,
    FirmwareEngineeringPort,
    FirmwareDebugAnalyzerPort,
    FirmwareFailureReference,
    FirmwareFramework,
    FirmwareParserPort,
    FirmwareProjectSnapshot,
    SourceProjection,
)
from embedded_copilot.debug_analysis.contracts import (
    DebugAnalysisSnapshot,
    DebugCategory,
    DebugFinding,
    DebugSeverity,
    DebugSourceType,
    DebugStatus,
)


class FakeFirmwareParserPort(FirmwareParserPort, FirmwareEngineeringPort):
    def parse(self, firmware_reference: str) -> FirmwareProjectSnapshot:
        project_id = firmware_reference.split(":", 1)[-1]
        source = SourceProjection.create(
            source_count=2,
            header_count=1,
            entry_points=("main",),
            interfaces=("camera", "uart"),
        )
        return FirmwareProjectSnapshot.create(
            project_id=project_id,
            firmware_reference=firmware_reference,
            framework=FirmwareFramework.ESP_IDF,
            targets=("esp32",),
            source_projection=source,
            build_configuration=BuildConfigurationProjection(
                target="esp32",
                profile="debug",
                configuration_reference=f"config:{project_id}",
            ),
        )

    def get_snapshot(self, project_id: str) -> FirmwareProjectSnapshot:
        return self.parse(f"firmware:{project_id}")


class FakeFirmwareBuildPort(FirmwareBuildPort):
    def request(
        self,
        project_id: str,
        firmware_reference: str,
        build_profile: str,
        approval_reference: str | None,
    ) -> FirmwareBuildRequest:
        return FirmwareBuildRequest.create(
            project_id=project_id,
            firmware_reference=firmware_reference,
            build_profile=build_profile,
            approval_reference=approval_reference,
        )

    def build(self, request: FirmwareBuildRequest) -> FirmwareBuildResult:
        return FirmwareBuildResult.create(
            status=FirmwareBuildStatus.SUCCESS,
            artifact_reference=request.firmware_reference,
            build_status=FirmwareBuildStatus.SUCCESS,
            summary="Deterministic firmware build projection.",
        )

    def get_snapshot(self, project_id: str) -> FirmwareBuildResult:
        return FirmwareBuildResult.create(
            status=FirmwareBuildStatus.READY,
            artifact_reference=f"firmware:{project_id}",
            build_status=FirmwareBuildStatus.READY,
            summary="Firmware build is ready for an approved build action.",
        )


class FakeFirmwareDebugAnalyzer(FirmwareDebugAnalyzerPort):
    def analyze(self, failure: FirmwareFailureReference) -> DebugAnalysisSnapshot:
        finding = DebugFinding.create(
            finding_id=f"finding:{failure.project_id}:firmware",
            project_id=failure.project_id,
            source_type=DebugSourceType.BUILD,
            category=DebugCategory.UNKNOWN,
            severity=DebugSeverity.MEDIUM,
            summary="Firmware failure requires structured review.",
            evidence_reference=failure.evidence_reference,
            status=DebugStatus.PROJECTED,
        )
        return DebugAnalysisSnapshot.create(
            project_id=failure.project_id,
            failure_reference=failure.evidence_reference,
            findings=(finding,),
        )


__all__ = ["FakeFirmwareBuildPort", "FakeFirmwareDebugAnalyzer", "FakeFirmwareParserPort"]
