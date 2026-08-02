from __future__ import annotations

from embedded_copilot.engineering_firmware import (
    BuildArtifactStatus,
    FirmwareDiagnosticCategory,
    FirmwareFindingCode,
    FirmwareModuleLayer,
    FirmwarePriorityRecommendation,
    FirmwareTaskType,
    create_engineering_firmware_runtime,
)


def test_runtime_builds_complete_proposal_without_execution(firmware_request) -> None:
    runtime = create_engineering_firmware_runtime()
    port = runtime.firmware_engineering_port()

    proposal = port.prepare_firmware_proposal(firmware_request)

    assert tuple(item.layer for item in proposal.architecture.modules) == tuple(
        FirmwareModuleLayer
    )
    assert proposal.driver_design.drivers
    assert tuple(item.task_type for item in proposal.task_architecture.tasks) == (
        FirmwareTaskType.CAMERA,
        FirmwareTaskType.NETWORK,
    )
    assert all(
        item.priority_recommendation is FirmwarePriorityRecommendation.UNRESOLVED
        for item in proposal.task_architecture.tasks
    )
    assert proposal.interface_contracts.contracts
    assert proposal.code_generation.intents
    assert proposal.build.artifact_status is BuildArtifactStatus.UNAVAILABLE
    assert proposal.build.command_available is False
    assert tuple(item.category for item in proposal.debug_strategy.strategies) == (
        FirmwareDiagnosticCategory.COMPILE_ERROR,
    )
    assert proposal.execution_contract.execution_available is False
    assert proposal.execution_contract.execution_state == "PROPOSAL_ONLY"
    assert proposal.review.review_required is True
    assert proposal.candidate_semantics == "unverified"


def test_proposal_does_not_expose_code_hardware_or_build_artifacts(
    firmware_request,
) -> None:
    proposal = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(firmware_request)
    )
    serialized = proposal.model_dump_json().casefold()
    forbidden = (
        "binary_path",
        "source_code",
        "file_content",
        "register_value",
        "pin_mapping",
        "stdout",
        "stderr",
        "idf.py",
        "openocd",
    )
    assert not any(item in serialized for item in forbidden)
    assert all(not item.pin_bindings for item in proposal.interface_contracts.contracts)
    assert all(
        item.register_bindings == ()
        and item.clock_configuration is None
        and item.memory_layout is None
        for item in proposal.interface_contracts.contracts
    )


def test_review_keeps_unresolved_and_execution_findings(firmware_request) -> None:
    proposal = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(firmware_request)
    )
    assert (
        FirmwareFindingCode.INTERFACE_DETAIL_UNRESOLVED in proposal.review.finding_codes
    )
    assert FirmwareFindingCode.TASK_PRIORITY_UNRESOLVED in proposal.review.finding_codes
    assert FirmwareFindingCode.EXECUTION_NOT_AVAILABLE in proposal.review.finding_codes
    assert (
        FirmwareFindingCode.DEBUG_EVIDENCE_REQUIRED not in proposal.review.finding_codes
    )


def test_runtime_keeps_all_caller_owned_inputs_unchanged(firmware_request) -> None:
    before = firmware_request.model_dump(mode="python")
    proposal = (
        create_engineering_firmware_runtime()
        .firmware_engineering_port()
        .prepare_firmware_proposal(firmware_request)
    )
    assert firmware_request.model_dump(mode="python") == before
    assert (
        proposal.hardware_proposal_fingerprint
        == firmware_request.hardware_proposal.fingerprint
    )
