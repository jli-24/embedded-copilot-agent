from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_artifacts import (
    ArtifactType,
    create_engineering_artifact_runtime,
)
from embedded_copilot.engineering_execution import (
    BuildExecutionInput,
    BuildResult,
    BuildResultStatus,
    DebugDiagnosticType,
    DebugExecutionInput,
    EngineeringExecutionRequest,
    EngineeringExecutionType,
    ExecutableArtifactReference,
    ExecutableArtifactStatus,
    ExecutionAdapterMetadata,
    ExecutionApprovalContract,
    ExecutionApprovalStatus,
    ExecutionPolicy,
    ExecutionPolicyStatus,
    ExecutionToolType,
    FlashExecutionInput,
    build_execution_input_fingerprint,
    build_result_fingerprint,
    debug_execution_input_fingerprint,
    engineering_execution_request_fingerprint,
    executable_artifact_reference_fingerprint,
    execution_adapter_metadata_fingerprint,
    execution_approval_fingerprint,
    execution_policy_fingerprint,
    flash_execution_input_fingerprint,
)
from tests.engineering_artifacts import conftest as _artifact_fixtures

firmware_request = _artifact_fixtures.firmware_request
validation_setup = _artifact_fixtures.validation_setup
generation_request = _artifact_fixtures.generation_request

NOW = datetime(2026, 8, 8, 9, 0, tzinfo=UTC)


@pytest.fixture
def artifact_report(generation_request):
    return (
        create_engineering_artifact_runtime()
        .engineering_artifact_port()
        .generate(generation_request)
    )


def artifact_entry(contract, artifact_type=ArtifactType.FIRMWARE_STRUCTURE):
    return next(
        item for item in contract.artifacts if item.artifact_type is artifact_type
    )


def make_metadata(
    execution_type: EngineeringExecutionType = EngineeringExecutionType.BUILD,
    *,
    binding_id: str = "build-adapter-1",
    tool_type: ExecutionToolType = ExecutionToolType.BUILD_ADAPTER,
) -> ExecutionAdapterMetadata:
    values = dict(
        binding_id=binding_id,
        execution_type=execution_type,
        tool_type=tool_type,
    )
    return ExecutionAdapterMetadata(
        **values,
        fingerprint=execution_adapter_metadata_fingerprint(**values),
    )


def make_build_input(contract) -> BuildExecutionInput:
    target = artifact_entry(contract)
    values = dict(
        kind=EngineeringExecutionType.BUILD,
        artifact_type=ArtifactType.FIRMWARE_STRUCTURE,
        artifact_fingerprint=target.artifact_fingerprint,
    )
    return BuildExecutionInput(
        **values,
        fingerprint=build_execution_input_fingerprint(**values),
    )


def make_flash_input(contract) -> FlashExecutionInput:
    target = artifact_entry(contract)
    reference_values = dict(
        reference_id="firmware-image-reference-1",
        source_artifact_fingerprint=target.artifact_fingerprint,
        artifact_fingerprint="sha256:" + "a" * 64,
        status=ExecutableArtifactStatus.AVAILABLE,
    )
    reference = ExecutableArtifactReference(
        **reference_values,
        fingerprint=executable_artifact_reference_fingerprint(**reference_values),
    )
    values = dict(
        kind=EngineeringExecutionType.FLASH,
        artifact_type=ArtifactType.FIRMWARE_STRUCTURE,
        artifact_fingerprint=target.artifact_fingerprint,
        executable_artifact=reference,
    )
    return FlashExecutionInput(
        **values,
        fingerprint=flash_execution_input_fingerprint(**values),
    )


def make_build_result(
    artifact_fingerprint: str,
    *,
    status: BuildResultStatus = BuildResultStatus.SUCCESS,
    finding_codes: tuple[str, ...] = (),
) -> BuildResult:
    values = dict(
        artifact_fingerprint=artifact_fingerprint,
        tool_type=ExecutionToolType.BUILD_ADAPTER,
        status=status,
        finding_codes=finding_codes,
    )
    return BuildResult(
        **values,
        fingerprint=build_result_fingerprint(**values),
    )


def make_debug_input(contract, validation_report) -> DebugExecutionInput:
    target = artifact_entry(contract)
    build_result = make_build_result(target.artifact_fingerprint)
    values = dict(
        kind=EngineeringExecutionType.DEBUG,
        artifact_type=ArtifactType.FIRMWARE_STRUCTURE,
        artifact_fingerprint=target.artifact_fingerprint,
        build_result=build_result,
        validation_report=validation_report,
        diagnostic_types=(
            DebugDiagnosticType.COMPILE_ERROR,
            DebugDiagnosticType.RUNTIME_ERROR,
            DebugDiagnosticType.MEMORY_ISSUE,
        ),
    )
    return DebugExecutionInput(
        **values,
        fingerprint=debug_execution_input_fingerprint(**values),
    )


def make_request(
    artifact_report,
    *,
    execution_type: EngineeringExecutionType = EngineeringExecutionType.BUILD,
    execution_input=None,
    approval_status: ExecutionApprovalStatus = ExecutionApprovalStatus.APPROVED,
    policy_status: ExecutionPolicyStatus = ExecutionPolicyStatus.ALLOWED,
    adapter_binding_id: str | None = None,
) -> EngineeringExecutionRequest:
    contract = artifact_report.artifact_contract
    if execution_input is None:
        if execution_type is EngineeringExecutionType.BUILD:
            execution_input = make_build_input(contract)
        elif execution_type is EngineeringExecutionType.FLASH:
            execution_input = make_flash_input(contract)
        else:
            execution_input = make_debug_input(
                contract,
                artifact_report.validation_report_fingerprint,
            )
    if adapter_binding_id is None:
        adapter_binding_id = {
            EngineeringExecutionType.BUILD: "build-adapter-1",
            EngineeringExecutionType.FLASH: "flash-adapter-1",
            EngineeringExecutionType.DEBUG: "debug-adapter-1",
        }[execution_type]
    policy_values = dict(
        policy_id="execution-policy-1",
        execution_id="execution-1",
        artifact_contract_fingerprint=contract.fingerprint,
        artifact_source_fingerprint=contract.artifact_source_fingerprint,
        execution_type=execution_type,
        execution_input_fingerprint=execution_input.fingerprint,
        adapter_binding_id=adapter_binding_id,
        status=policy_status,
    )
    policy = ExecutionPolicy(
        **policy_values,
        fingerprint=execution_policy_fingerprint(**policy_values),
    )
    reviewed = approval_status is not ExecutionApprovalStatus.PENDING
    approval_values = dict(
        execution_id="execution-1",
        artifact_contract_fingerprint=contract.fingerprint,
        artifact_source_fingerprint=contract.artifact_source_fingerprint,
        execution_type=execution_type,
        execution_input_fingerprint=execution_input.fingerprint,
        execution_policy_fingerprint=policy.fingerprint,
        status=approval_status,
        reviewer="reviewer-1" if reviewed else None,
        reviewed_at=NOW if reviewed else None,
    )
    approval = ExecutionApprovalContract(
        **approval_values,
        fingerprint=execution_approval_fingerprint(**approval_values),
    )
    request_values = dict(
        execution_id="execution-1",
        artifact_contract=contract,
        artifact_source_fingerprint=contract.artifact_source_fingerprint,
        execution_type=execution_type,
        execution_input=execution_input,
        approval_context=approval,
        execution_policy=policy,
        requested_at=NOW,
    )
    return EngineeringExecutionRequest(
        **request_values,
        fingerprint=engineering_execution_request_fingerprint(**request_values),
    )
