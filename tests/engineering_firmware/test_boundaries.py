from __future__ import annotations

import pytest

from embedded_copilot.engineering_firmware import (
    FirmwareBuildArtifactType,
    FirmwareBuildSystem,
    FirmwareEngineeringRejected,
    FirmwareEngineeringRequest,
    FirmwareFindingCode,
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
    RequirementConstraint,
    create_engineering_intelligence_runtime,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringRequirementDocument,
    context_snapshot_fingerprint,
    requirement_document_fingerprint,
)


def _platform(
    *,
    hardware,
    requirement,
    context,
    profile=FirmwarePlatformProfile.UNRESOLVED,
    build_system=FirmwareBuildSystem.UNRESOLVED,
    toolchain=FirmwareToolchainRequirement.UNRESOLVED,
    status=FirmwarePlatformStatus.UNRESOLVED,
    evidence_ids=(),
) -> FirmwarePlatformProjection:
    values = dict(
        project_id=requirement.project_id,
        requirement_fingerprint=requirement.fingerprint,
        hardware_proposal_fingerprint=hardware.fingerprint,
        context_fingerprint=context.fingerprint,
        platform_profile=profile,
        build_system=build_system,
        toolchain_requirement=toolchain,
        status=status,
        evidence_ids=evidence_ids,
    )
    return FirmwarePlatformProjection(
        **values,
        fingerprint=firmware_platform_fingerprint(**values),
    )


def test_mcu_identity_never_selects_a_build_platform_implicitly(
    firmware_request,
) -> None:
    platform = _platform(
        hardware=firmware_request.hardware_proposal,
        requirement=firmware_request.requirement,
        context=firmware_request.context,
    )
    request = FirmwareEngineeringRequest(
        proposal_id="firmware-proposal-unresolved",
        hardware_proposal=firmware_request.hardware_proposal,
        requirement=firmware_request.requirement,
        context=firmware_request.context,
        platform=platform,
        proposed_at=firmware_request.proposed_at,
    )

    proposal = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(request)
    )

    assert proposal.platform.platform_profile is FirmwarePlatformProfile.UNRESOLVED
    assert proposal.build.build_system is FirmwareBuildSystem.UNRESOLVED
    assert proposal.build.expected_artifact_type is FirmwareBuildArtifactType.UNRESOLVED
    assert FirmwareFindingCode.PLATFORM_UNRESOLVED in proposal.review.finding_codes
    assert (
        FirmwareFindingCode.BUILD_CONFIGURATION_UNRESOLVED
        in proposal.review.finding_codes
    )


def test_hardware_conflict_is_preserved_for_review(firmware_request) -> None:
    original = firmware_request.requirement
    requirement_values = dict(
        project_id=original.project_id,
        session_id=original.session_id,
        message_id=original.message_id,
        product=original.product,
        functional_requirements=original.functional_requirements,
        performance_requirements=original.performance_requirements,
        hardware_constraints=(
            RequirementConstraint(key="MCU", value="ESP32-S3"),
            RequirementConstraint(key="MCU", value="STM32H7"),
        ),
        software_constraints=original.software_constraints,
        power_requirements=original.power_requirements,
        communication_requirements=original.communication_requirements,
        review_required=True,
    )
    requirement = EngineeringRequirementDocument(
        **requirement_values,
        fingerprint=requirement_document_fingerprint(**requirement_values),
    )
    intelligence_port = (
        create_engineering_intelligence_runtime().engineering_intelligence_port()
    )
    plan = intelligence_port.create_plan(requirement)
    context_values = dict(
        project=firmware_request.context.project,
        requirement_fingerprint=requirement.fingerprint,
        plan_fingerprint=plan.fingerprint,
        evidence=firmware_request.context.evidence,
        decisions=(),
        confidence=firmware_request.context.confidence,
        conflict_count=0,
        review_required=True,
    )
    context = type(firmware_request.context)(
        **context_values,
        fingerprint=context_snapshot_fingerprint(**context_values),
    )
    hardware = (
        create_engineering_hardware_runtime()
        .hardware_engineering_port()
        .prepare_proposal(
            HardwareEngineeringRequest(
                proposal_id="hardware-proposal-conflict",
                requirement=requirement,
                plan=plan,
                context=context,
                proposed_at=firmware_request.proposed_at,
            )
        )
    )
    platform = _platform(
        hardware=hardware,
        requirement=requirement,
        context=context,
    )
    request = FirmwareEngineeringRequest(
        proposal_id="firmware-proposal-conflict",
        hardware_proposal=hardware,
        requirement=requirement,
        context=context,
        platform=platform,
        proposed_at=firmware_request.proposed_at,
    )

    proposal = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(request)
    )

    assert (
        FirmwareFindingCode.HARDWARE_CONFLICT_REQUIRES_REVIEW
        in proposal.review.finding_codes
    )
    assert any(
        item.status.value == "BLOCKED" for item in proposal.driver_design.drivers
    )


def test_rejected_input_uses_a_sanitized_error() -> None:
    port = create_engineering_firmware_runtime().firmware_engineering_port()
    with pytest.raises(FirmwareEngineeringRejected) as captured:
        port.prepare_firmware_proposal(object())
    assert str(captured.value) == "firmware engineering request rejected"
