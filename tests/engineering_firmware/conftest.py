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

NOW = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def _evidence(
    *,
    evidence_id: str,
    fact_type: str,
    key: str,
    value: str,
    status: EvidenceStatus = EvidenceStatus.VERIFIED,
) -> EngineeringKnowledgeEvidence:
    values = dict(
        evidence_id=evidence_id,
        source_type=EngineeringKnowledgeSourceType.DATASHEET,
        fact_type=fact_type,
        key=key,
        value=value,
        summary="Safe structured engineering evidence.",
        status=status,
        confidence=1.0 if status is EvidenceStatus.VERIFIED else 0.5,
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
            "Design an ESP32-S3 camera with OV2640, Wi-Fi, ESP-IDF, and FreeRTOS."
        ),
        evidence=(
            _evidence(
                evidence_id="evidence-debug-compile",
                fact_type="FIRMWARE_COMPILE_ERROR",
                key="diagnostic",
                value="COMPILE_DIAGNOSTIC_AVAILABLE",
            ),
            _evidence(
                evidence_id="evidence-debug-memory-candidate",
                fact_type="FIRMWARE_MEMORY_ISSUE",
                key="diagnostic",
                value="MEMORY_DIAGNOSTIC_CANDIDATE",
                status=EvidenceStatus.CANDIDATE,
            ),
            _evidence(
                evidence_id="evidence-mcu",
                fact_type="COMPONENT_IDENTITY",
                key="mcu",
                value="ESP32-S3",
            ),
            _evidence(
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
