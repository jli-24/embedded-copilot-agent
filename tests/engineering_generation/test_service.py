from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_generation import (
    GenerationRequest,
    GenerationService,
    GenerationType,
)
from embedded_copilot.engineering_intelligence import (
    ContextStage,
    EngineeringContextInputProjection,
    EvidenceSourceType,
    EvidenceTrustBasis,
    build_context_snapshot,
    build_evidence,
    build_recommendation,
    fuse_evidence,
)


def _inputs():
    context = build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="ESP32 Camera",
            stage=ContextStage.PCB_DESIGN,
            decision_topic="camera interface",
            constraints=("low power",),
        )
    )
    knowledge = fuse_evidence(
        (
            build_evidence(
                evidence_id="e-1",
                source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary="Camera interface candidate",
                reference_id="ref-1",
                confidence=0.5,
                source_rank=0,
            ),
        )
    )
    return context, build_recommendation(context, knowledge)


def test_firmware_generation_is_projection_only_and_deterministic() -> None:
    context, recommendation = _inputs()
    request = GenerationRequest(
        project_id="project-1",
        generation_type=GenerationType.FIRMWARE,
        context_snapshot=context,
        recommendation=recommendation,
    )
    before = request.model_dump(mode="json")
    results = tuple(GenerationService().generate(request) for _ in range(100))
    assert len(set(item.fingerprint for item in results)) == 1
    artifact = results[0]
    assert artifact.artifact_type.value == "FIRMWARE"
    assert all("/" not in name and "\\" not in name for name in artifact.files)
    assert "content" not in artifact.model_dump()
    assert "main.c" in artifact.files
    assert request.model_dump(mode="json") == before


def test_hardware_generation_is_structured_and_does_not_invent_specs() -> None:
    context, recommendation = _inputs()
    request = GenerationRequest(
        project_id="project-1",
        generation_type=GenerationType.HARDWARE,
        context_snapshot=context,
        recommendation=recommendation,
    )
    artifact = GenerationService().generate(request)
    assert artifact.artifact_type.value == "HARDWARE"
    assert artifact.system_architecture.components
    assert artifact.interfaces
    assert artifact.bom
    serialized = str(artifact.model_dump(mode="json"))
    assert "GPIO12" not in serialized
    assert "80MHz" not in serialized
    assert "3.3V" not in serialized


def test_request_identity_and_tampering_are_rejected() -> None:
    context, recommendation = _inputs()
    with pytest.raises(ValidationError):
        GenerationRequest(
            project_id="other-project",
            generation_type=GenerationType.FIRMWARE,
            context_snapshot=context,
            recommendation=recommendation,
        )
    tampered = copy.deepcopy(context)
    object.__setattr__(tampered, "project_name", "tampered")
    with pytest.raises((ValidationError, ValueError, TypeError)):
        GenerationService().generate(
            GenerationRequest(
                project_id="project-1",
                generation_type=GenerationType.FIRMWARE,
                context_snapshot=tampered,
                recommendation=recommendation,
            )
        )
