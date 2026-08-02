"""Typed, deep-copied v0.53/v0.54 input boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from embedded_copilot.engineering_artifacts import (
    ArtifactType,
    EngineeringArtifactContract,
)
from embedded_copilot.engineering_execution.models import (
    BuildResult,
    DebugDiagnosticType,
    EngineeringExecutionType,
    ExecutableArtifactReference,
    ExecutionApprovalContract,
    ExecutionArtifactBinding,
    ExecutionArtifactStatus,
    ExecutionArtifactType,
    ExecutionPolicy,
    _ExecutionContract,
    _Fingerprinted,
    _fingerprint,
    _fingerprint_value,
    _identifier,
    _tuple,
    _utc,
    execution_artifact_binding_fingerprint,
)
from embedded_copilot.engineering_validation import HardwareValidationReport


class BuildExecutionInput(_Fingerprinted):
    kind: Literal[EngineeringExecutionType.BUILD] = EngineeringExecutionType.BUILD
    artifact_type: Literal[ArtifactType.FIRMWARE_STRUCTURE]
    artifact_fingerprint: str

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)


def build_execution_input_fingerprint(**values: object) -> str:
    values.setdefault("kind", EngineeringExecutionType.BUILD)
    return _fingerprint("BuildExecutionInput", **values)


class FlashExecutionInput(_Fingerprinted):
    kind: Literal[EngineeringExecutionType.FLASH] = EngineeringExecutionType.FLASH
    artifact_type: Literal[ArtifactType.FIRMWARE_STRUCTURE]
    artifact_fingerprint: str
    executable_artifact: ExecutableArtifactReference

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_executable_binding(self) -> FlashExecutionInput:
        if (
            self.executable_artifact.source_artifact_fingerprint
            != self.artifact_fingerprint
        ):
            raise ValueError("executable artifact binding mismatch")
        return self


def flash_execution_input_fingerprint(**values: object) -> str:
    values.setdefault("kind", EngineeringExecutionType.FLASH)
    return _fingerprint("FlashExecutionInput", **values)


class DebugExecutionInput(_Fingerprinted):
    kind: Literal[EngineeringExecutionType.DEBUG] = EngineeringExecutionType.DEBUG
    artifact_type: Literal[ArtifactType.FIRMWARE_STRUCTURE]
    artifact_fingerprint: str
    build_result: BuildResult
    validation_report: HardwareValidationReport
    diagnostic_types: tuple[DebugDiagnosticType, ...]

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)

    @field_validator("validation_report", mode="before")
    @classmethod
    def validate_typed_report(cls, value: object) -> object:
        if type(value) is not HardwareValidationReport:
            raise ValueError("typed validation report is required")
        return value

    @field_validator("diagnostic_types", mode="before")
    @classmethod
    def validate_diagnostic_tuple(cls, value: object) -> object:
        return _tuple(value, field="diagnostic_types")

    @model_validator(mode="after")
    def validate_debug_binding(self) -> DebugExecutionInput:
        order = {value: index for index, value in enumerate(DebugDiagnosticType)}
        keys = tuple(order[item] for item in self.diagnostic_types)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("diagnostic types must be sorted and unique")
        if self.build_result.artifact_fingerprint != self.artifact_fingerprint:
            raise ValueError("debug build result binding mismatch")
        return self


def debug_execution_input_fingerprint(**values: object) -> str:
    values.setdefault("kind", EngineeringExecutionType.DEBUG)
    return _fingerprint("DebugExecutionInput", **values)


ExecutionInput = Annotated[
    BuildExecutionInput | FlashExecutionInput | DebugExecutionInput,
    Field(discriminator="kind"),
]


class EngineeringExecutionRequest(_ExecutionContract):
    execution_id: str
    artifact_contract: EngineeringArtifactContract
    artifact_source_fingerprint: str
    execution_type: EngineeringExecutionType
    execution_input: ExecutionInput
    approval_context: ExecutionApprovalContract
    execution_policy: ExecutionPolicy
    requested_at: datetime
    fingerprint: str

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _source_fingerprint = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("artifact_contract", mode="before")
    @classmethod
    def validate_typed_contract(cls, value: object) -> object:
        if type(value) is not EngineeringArtifactContract:
            raise ValueError("typed artifact contract is required")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> EngineeringExecutionRequest:
        if self.execution_input.kind is not self.execution_type:
            raise ValueError("execution input type mismatch")
        if (
            self.artifact_source_fingerprint
            != self.artifact_contract.artifact_source_fingerprint
        ):
            raise ValueError("artifact source binding mismatch")
        policy = self.execution_policy
        approval = self.approval_context
        common = (
            self.execution_id,
            self.artifact_contract.fingerprint,
            self.artifact_source_fingerprint,
            self.execution_type,
            self.execution_input.fingerprint,
        )
        if (
            (
                policy.execution_id,
                policy.artifact_contract_fingerprint,
                policy.artifact_source_fingerprint,
                policy.execution_type,
                policy.execution_input_fingerprint,
            )
            != common
            or (
                approval.execution_id,
                approval.artifact_contract_fingerprint,
                approval.artifact_source_fingerprint,
                approval.execution_type,
                approval.execution_input_fingerprint,
            )
            != common
            or approval.execution_policy_fingerprint != policy.fingerprint
        ):
            raise ValueError("execution binding mismatch")
        expected = engineering_execution_request_fingerprint(
            execution_id=self.execution_id,
            artifact_contract=self.artifact_contract,
            artifact_source_fingerprint=self.artifact_source_fingerprint,
            execution_type=self.execution_type,
            execution_input=self.execution_input,
            approval_context=self.approval_context,
            execution_policy=self.execution_policy,
            requested_at=self.requested_at,
        )
        if self.fingerprint != expected:
            raise ValueError("execution request fingerprint mismatch")
        return self


def engineering_execution_request_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringExecutionRequest", **values)


@dataclass(frozen=True, slots=True)
class _ValidationProjection:
    report_fingerprint: str
    finding_codes: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ProjectedExecutionRequest:
    request: EngineeringExecutionRequest
    artifact: ExecutionArtifactBinding
    artifact_review_required: bool
    validation: _ValidationProjection | None


def project_request(value: object) -> _ProjectedExecutionRequest:
    if type(value) is not EngineeringExecutionRequest:
        raise TypeError("typed engineering execution request is required")
    if (
        type(value.artifact_contract) is not EngineeringArtifactContract
        or type(value.execution_policy) is not ExecutionPolicy
        or type(value.approval_context) is not ExecutionApprovalContract
        or type(value.execution_input)
        not in (BuildExecutionInput, FlashExecutionInput, DebugExecutionInput)
    ):
        raise TypeError("typed engineering execution inputs are required")
    if isinstance(value.execution_input, DebugExecutionInput) and (
        type(value.execution_input.build_result) is not BuildResult
        or type(value.execution_input.validation_report) is not HardwareValidationReport
    ):
        raise TypeError("typed debug inputs are required")
    copied = value.model_copy(deep=True)
    checked = EngineeringExecutionRequest.model_validate(copied)
    target = next(
        (
            item
            for item in checked.artifact_contract.artifacts
            if item.artifact_type is checked.execution_input.artifact_type
        ),
        None,
    )
    if (
        target is None
        or target.artifact_fingerprint != checked.execution_input.artifact_fingerprint
    ):
        raise ValueError("target artifact binding mismatch")
    validation = None
    if isinstance(checked.execution_input, DebugExecutionInput):
        report = checked.execution_input.validation_report
        source_fingerprints = {
            source.source_fingerprint
            for binding in checked.artifact_contract.source_bindings
            for source in binding.sources
        }
        required = {
            report.requirement_fingerprint,
            report.context_fingerprint,
            report.hardware_proposal_fingerprint,
            report.firmware_proposal_fingerprint,
        }
        if not required.issubset(source_fingerprints):
            raise ValueError("validation source binding mismatch")
        validation = _ValidationProjection(
            report_fingerprint=report.fingerprint,
            finding_codes=tuple(
                sorted(item.value for item in report.review.finding_codes)
            ),
            evidence_reference_ids=tuple(
                sorted(
                    {
                        reference
                        for evidence in report.evidence_trace
                        for reference in evidence.reference_ids
                    }
                )
            ),
        )
    artifact_values = dict(
        artifact_contract_fingerprint=checked.artifact_contract.fingerprint,
        artifact_source_fingerprint=checked.artifact_source_fingerprint,
        artifact_type=ExecutionArtifactType(target.artifact_type.value),
        artifact_status=ExecutionArtifactStatus(target.status.value),
        artifact_fingerprint=target.artifact_fingerprint,
    )
    artifact = ExecutionArtifactBinding(
        **artifact_values,
        fingerprint=execution_artifact_binding_fingerprint(**artifact_values),
    )
    return _ProjectedExecutionRequest(
        request=checked,
        artifact=artifact,
        artifact_review_required=target.status.value == "REVIEW_REQUIRED",
        validation=validation,
    )


def revalidate_artifact_binding(
    artifact: ExecutionArtifactBinding,
    *,
    expected_fingerprint: str,
) -> bool:
    if type(artifact) is not ExecutionArtifactBinding:
        return False
    try:
        checked = ExecutionArtifactBinding.model_validate(
            artifact.model_copy(deep=True)
        )
    except (TypeError, ValueError):
        return False
    return checked.fingerprint == expected_fingerprint
