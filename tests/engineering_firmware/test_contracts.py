from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_firmware import (
    FirmwareBuildSystem,
    FirmwareEngineeringRequest,
    FirmwarePlatformProfile,
    FirmwarePlatformProjection,
    FirmwarePlatformStatus,
    FirmwareToolchainRequirement,
    firmware_platform_fingerprint,
)


def test_firmware_contracts_are_frozen_strict_and_tuple_only(firmware_request) -> None:
    with pytest.raises((ValidationError, FrozenInstanceError)):
        firmware_request.proposal_id = "changed"

    payload = {
        "proposal_id": firmware_request.proposal_id,
        "hardware_proposal": firmware_request.hardware_proposal,
        "requirement": firmware_request.requirement,
        "context": firmware_request.context,
        "platform": firmware_request.platform,
        "proposed_at": firmware_request.proposed_at,
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        FirmwareEngineeringRequest.model_validate(payload)

    platform_payload = firmware_request.platform.model_dump(mode="python")
    platform_payload["evidence_ids"] = ["evidence-platform"]
    with pytest.raises(ValidationError):
        FirmwarePlatformProjection.model_validate(platform_payload)


def test_platform_contract_rejects_unsupported_combinations(firmware_request) -> None:
    values = dict(
        project_id=firmware_request.requirement.project_id,
        requirement_fingerprint=firmware_request.requirement.fingerprint,
        hardware_proposal_fingerprint=firmware_request.hardware_proposal.fingerprint,
        context_fingerprint=firmware_request.context.fingerprint,
        platform_profile=FirmwarePlatformProfile.ESP_IDF_FREERTOS,
        build_system=FirmwareBuildSystem.CMAKE,
        toolchain_requirement=FirmwareToolchainRequirement.ARM_GNU_TOOLCHAIN,
        status=FirmwarePlatformStatus.PROPOSED,
        evidence_ids=(),
    )
    with pytest.raises(ValidationError):
        FirmwarePlatformProjection(
            **values,
            fingerprint=firmware_platform_fingerprint(**values),
        )


def test_supported_platform_requires_matching_verified_evidence(
    firmware_request,
) -> None:
    values = dict(
        project_id=firmware_request.requirement.project_id,
        requirement_fingerprint=firmware_request.requirement.fingerprint,
        hardware_proposal_fingerprint=firmware_request.hardware_proposal.fingerprint,
        context_fingerprint=firmware_request.context.fingerprint,
        platform_profile=FirmwarePlatformProfile.ESP_IDF_FREERTOS,
        build_system=FirmwareBuildSystem.ESP_IDF,
        toolchain_requirement=FirmwareToolchainRequirement.ESP_IDF_TOOLCHAIN,
        status=FirmwarePlatformStatus.SUPPORTED,
        evidence_ids=("evidence-mcu",),
    )
    platform = FirmwarePlatformProjection(
        **values,
        fingerprint=firmware_platform_fingerprint(**values),
    )
    with pytest.raises(ValidationError):
        FirmwareEngineeringRequest(
            proposal_id="firmware-proposal-invalid",
            hardware_proposal=firmware_request.hardware_proposal,
            requirement=firmware_request.requirement,
            context=firmware_request.context,
            platform=platform,
            proposed_at=firmware_request.proposed_at,
        )
