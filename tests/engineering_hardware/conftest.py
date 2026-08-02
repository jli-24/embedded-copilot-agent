from __future__ import annotations

from datetime import UTC, datetime

import pytest

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

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)


def evidence(
    *,
    evidence_id: str,
    key: str,
    value: str,
    status: EvidenceStatus = EvidenceStatus.VERIFIED,
    fact_type: str = "COMPONENT_IDENTITY",
) -> EngineeringKnowledgeEvidence:
    values = dict(
        evidence_id=evidence_id,
        source_type=EngineeringKnowledgeSourceType.DATASHEET,
        fact_type=fact_type,
        key=key,
        value=value,
        summary="Structured engineering evidence reference.",
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
def intelligence_snapshot():
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
    request = EngineeringIntelligenceRequest(
        project=project_engineering_project(interface_project),
        session_id="session-1",
        message_id="message-1",
        requirement_summary=(
            "Design an ESP32-S3 camera with OV2640, Wi-Fi, and low power."
        ),
        evidence=(
            evidence(evidence_id="evidence-mcu", key="mcu", value="ESP32-S3"),
            evidence(
                evidence_id="evidence-camera-candidate",
                key="camera",
                value="OV2640",
                status=EvidenceStatus.CANDIDATE,
            ),
        ),
        requested_at=NOW,
    )
    return (
        create_engineering_intelligence_runtime()
        .engineering_intelligence_port()
        .prepare_project(request)
    )
