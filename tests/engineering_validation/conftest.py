from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_firmware import (
    FirmwareBuildSystem,
    FirmwareEngineeringRequest,
    FirmwarePlatformProfile,
    FirmwarePlatformProjection,
    FirmwarePlatformStatus,
    FirmwareToolchainRequirement,
    create_engineering_firmware_runtime,
    firmware_platform_fingerprint,
)
from embedded_copilot.engineering_hardware import (
    HardwareEngineeringRequest,
    create_engineering_hardware_runtime,
)
from embedded_copilot.engineering_intelligence import (
    EngineeringIntelligenceRequest,
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EvidenceStatus,
    create_engineering_intelligence_runtime,
    engineering_evidence_fingerprint,
    project_engineering_project,
)
from embedded_copilot.engineering_interface import (
    EngineeringProjectProjection,
    engineering_project_fingerprint,
)
from embedded_copilot.engineering_validation import (
    DeviceEvidenceCollectionResult,
    EvidenceMetricUnit,
    EvidenceOutcome,
    EvidenceQualification,
    EvidenceRecord,
    EvidenceSafeMetadata,
    EvidenceSnapshot,
    EvidenceSourceType,
    EvidenceType,
    HardwareValidationRequest,
    ValidationTestType,
    device_evidence_collection_result_fingerprint,
    evidence_record_fingerprint,
    evidence_safe_metadata_fingerprint,
    evidence_snapshot_fingerprint,
)

NOW = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)


def _knowledge_evidence(
    *, evidence_id: str, fact_type: str, key: str, value: str
) -> EngineeringKnowledgeEvidence:
    values = dict(
        evidence_id=evidence_id,
        source_type=EngineeringKnowledgeSourceType.DATASHEET,
        fact_type=fact_type,
        key=key,
        value=value,
        summary="Safe structured engineering evidence.",
        status=EvidenceStatus.VERIFIED,
        confidence=1.0,
        reference_ids=(f"reference-{evidence_id}",),
        observed_at=NOW,
    )
    return EngineeringKnowledgeEvidence(
        **values,
        fingerprint=engineering_evidence_fingerprint(**values),
    )


@pytest.fixture
def firmware_request() -> FirmwareEngineeringRequest:
    project_values = dict(
        project_id="project-1",
        name="ESP32-S3 Smart Camera",
        summary="A reviewable smart camera engineering project.",
        reference_ids=("board-esp32-s3",),
    )
    interface_project = EngineeringProjectProjection(
        **project_values,
        fingerprint=engineering_project_fingerprint(**project_values),
    )
    intelligence_request = EngineeringIntelligenceRequest(
        project=project_engineering_project(interface_project),
        session_id="session-1",
        message_id="message-1",
        requirement_summary=(
            "Design an ESP32-S3 camera with OV2640, Wi-Fi, ESP-IDF, FreeRTOS, "
            "and low power."
        ),
        evidence=(
            _knowledge_evidence(
                evidence_id="evidence-mcu",
                fact_type="COMPONENT_IDENTITY",
                key="mcu",
                value="ESP32-S3",
            ),
            _knowledge_evidence(
                evidence_id="evidence-platform",
                fact_type="FIRMWARE_PLATFORM_PROFILE",
                key="platform",
                value="ESP_IDF_FREERTOS",
            ),
        ),
        requested_at=NOW,
    )
    intelligence = (
        create_engineering_intelligence_runtime()
        .engineering_intelligence_port()
        .prepare_project(intelligence_request)
    )
    hardware = (
        create_engineering_hardware_runtime()
        .hardware_engineering_port()
        .prepare_proposal(
            HardwareEngineeringRequest(
                proposal_id="hardware-proposal-1",
                requirement=intelligence.requirement,
                plan=intelligence.plan,
                context=intelligence.context,
                proposed_at=NOW,
            )
        )
    )
    platform_values = dict(
        project_id=intelligence.requirement.project_id,
        requirement_fingerprint=intelligence.requirement.fingerprint,
        hardware_proposal_fingerprint=hardware.fingerprint,
        context_fingerprint=intelligence.context.fingerprint,
        platform_profile=FirmwarePlatformProfile.ESP_IDF_FREERTOS,
        build_system=FirmwareBuildSystem.ESP_IDF,
        toolchain_requirement=FirmwareToolchainRequirement.ESP_IDF_TOOLCHAIN,
        status=FirmwarePlatformStatus.SUPPORTED,
        evidence_ids=("evidence-platform",),
    )
    platform = FirmwarePlatformProjection(
        **platform_values,
        fingerprint=firmware_platform_fingerprint(**platform_values),
    )
    return FirmwareEngineeringRequest(
        proposal_id="firmware-proposal-1",
        hardware_proposal=hardware,
        requirement=intelligence.requirement,
        context=intelligence.context,
        platform=platform,
        proposed_at=NOW,
    )


def make_record(
    *,
    evidence_id: str,
    test_type: ValidationTestType,
    evidence_type: EvidenceType,
    outcome: EvidenceOutcome,
    qualification: EvidenceQualification = EvidenceQualification.VERIFIED,
    source_type: EvidenceSourceType = EvidenceSourceType.CALLER_PROVIDED,
    observation_code: str = "OBSERVATION_AVAILABLE",
    metric_name: str | None = None,
    metric_value: int | float | None = None,
    metric_unit: EvidenceMetricUnit | None = None,
) -> EvidenceRecord:
    metadata_values = dict(
        test_type=test_type,
        outcome=outcome,
        observation_code=observation_code,
        metric_name=metric_name,
        metric_value=metric_value,
        metric_unit=metric_unit,
        sample_count=1,
        reference_ids=(f"reference-{evidence_id}",),
        observed_at=NOW,
    )
    metadata = EvidenceSafeMetadata(
        **metadata_values,
        fingerprint=evidence_safe_metadata_fingerprint(**metadata_values),
    )
    values = dict(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_type=source_type,
        qualification=qualification,
        safe_metadata=metadata,
    )
    return EvidenceRecord(
        **values,
        fingerprint=evidence_record_fingerprint(**values),
    )


def make_snapshot(
    firmware_request, records: tuple[EvidenceRecord, ...]
) -> EvidenceSnapshot:
    values = dict(
        snapshot_id="baseline-snapshot-1",
        project_id=firmware_request.requirement.project_id,
        requirement_fingerprint=firmware_request.requirement.fingerprint,
        hardware_proposal_fingerprint=firmware_request.hardware_proposal.fingerprint,
        firmware_proposal_fingerprint="sha256:" + "0" * 64,
        context_fingerprint=firmware_request.context.fingerprint,
        records=tuple(sorted(records, key=lambda item: item.evidence_id)),
        captured_at=NOW,
    )
    return EvidenceSnapshot(
        **values,
        fingerprint=evidence_snapshot_fingerprint(**values),
    )


class FakeEvidencePort:
    def __init__(self, records: tuple[EvidenceRecord, ...] = ()) -> None:
        self.records = records
        self.calls = []

    def collect(self, request):
        self.calls.append(request)
        values = dict(
            proposal_id=request.proposal_id,
            project_id=request.project_id,
            test_plan_fingerprint=request.test_plan.fingerprint,
            records=tuple(sorted(self.records, key=lambda item: item.evidence_id)),
            collected_at=request.requested_at,
        )
        return DeviceEvidenceCollectionResult(
            **values,
            fingerprint=device_evidence_collection_result_fingerprint(**values),
        )


@pytest.fixture
def validation_setup(firmware_request):
    firmware = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(firmware_request)
    )
    baseline = make_snapshot(
        firmware_request,
        (
            make_record(
                evidence_id="baseline-camera",
                test_type=ValidationTestType.CAMERA_CAPTURE,
                evidence_type=EvidenceType.FPS_RESULT,
                outcome=EvidenceOutcome.PASS,
                metric_name="frames_per_second",
                metric_value=20,
                metric_unit=EvidenceMetricUnit.FRAMES_PER_SECOND,
            ),
            make_record(
                evidence_id="candidate-network",
                test_type=ValidationTestType.NETWORK_CONNECTIVITY,
                evidence_type=EvidenceType.NETWORK_METRIC,
                outcome=EvidenceOutcome.FAIL,
                qualification=EvidenceQualification.CANDIDATE,
                metric_name="latency",
                metric_value=300,
                metric_unit=EvidenceMetricUnit.MILLISECONDS,
            ),
        ),
    )
    snapshot_values = baseline.model_dump(mode="python")
    snapshot_values["firmware_proposal_fingerprint"] = firmware.fingerprint
    snapshot_values.pop("fingerprint")
    baseline = EvidenceSnapshot(
        **snapshot_values,
        fingerprint=evidence_snapshot_fingerprint(**snapshot_values),
    )
    request = HardwareValidationRequest(
        proposal_id="validation-proposal-1",
        hardware_proposal=firmware_request.hardware_proposal,
        firmware_proposal=firmware,
        requirement=firmware_request.requirement,
        context=firmware_request.context,
        evidence_snapshot=baseline,
        proposed_at=NOW,
    )
    port = FakeEvidencePort(
        (
            make_record(
                evidence_id="collection-build",
                test_type=ValidationTestType.FIRMWARE_BUILD,
                evidence_type=EvidenceType.UART_LOG,
                outcome=EvidenceOutcome.PASS,
                source_type=EvidenceSourceType.MOCK,
                observation_code="BUILD_RESULT_AVAILABLE",
            ),
            make_record(
                evidence_id="collection-network",
                test_type=ValidationTestType.NETWORK_CONNECTIVITY,
                evidence_type=EvidenceType.NETWORK_METRIC,
                outcome=EvidenceOutcome.PASS,
                source_type=EvidenceSourceType.MOCK,
                metric_name="latency",
                metric_value=50,
                metric_unit=EvidenceMetricUnit.MILLISECONDS,
            ),
            make_record(
                evidence_id="collection-power",
                test_type=ValidationTestType.POWER_OBSERVATION,
                evidence_type=EvidenceType.POWER_MEASUREMENT,
                outcome=EvidenceOutcome.PASS,
                source_type=EvidenceSourceType.MOCK,
                metric_name="current",
                metric_value=100,
                metric_unit=EvidenceMetricUnit.MILLIAMPERES,
            ),
        )
    )
    return request, port
