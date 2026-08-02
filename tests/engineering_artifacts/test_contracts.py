from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_artifacts import (
    ArtifactSourceType,
    ArtifactStatus,
    ArtifactType,
    EngineeringArtifactPort,
    EngineeringArtifactRuntime,
    EngineeringGenerationRequest,
    create_engineering_artifact_runtime,
)


def test_request_is_frozen_strict_and_forbids_extra(generation_request) -> None:
    with pytest.raises(ValidationError):
        generation_request.proposal_id = "changed"
    payload = generation_request.model_dump(mode="python")
    payload["extra"] = True
    with pytest.raises(ValidationError):
        EngineeringGenerationRequest.model_validate(payload)


def test_factory_and_facade_are_narrow() -> None:
    runtime = create_engineering_artifact_runtime()
    assert isinstance(runtime, EngineeringArtifactRuntime)
    assert isinstance(runtime.engineering_artifact_port(), EngineeringArtifactPort)
    assert tuple(
        name
        for name, _ in inspect.getmembers(type(runtime), inspect.isfunction)
        if not name.startswith("_")
    ) == ("engineering_artifact_port",)


def test_contract_has_fixed_artifacts_and_typed_source_bindings(
    generation_request,
) -> None:
    report = (
        create_engineering_artifact_runtime()
        .engineering_artifact_port()
        .generate(generation_request)
    )
    contract = report.artifact_contract
    assert tuple(item.artifact_type for item in contract.artifacts) == tuple(
        ArtifactType
    )
    assert tuple(item.artifact_type for item in contract.source_bindings) == tuple(
        ArtifactType
    )
    assert contract.artifact_source_fingerprint.startswith("sha256:")
    firmware = contract.source_bindings[0]
    assert tuple(item.source_type for item in firmware.sources) == (
        ArtifactSourceType.REQUIREMENT,
        ArtifactSourceType.CONTEXT,
        ArtifactSourceType.HARDWARE_PROPOSAL,
        ArtifactSourceType.FIRMWARE_PROPOSAL,
    )
    assert all(
        item.status is not ArtifactStatus.UNAVAILABLE for item in contract.artifacts
    )
