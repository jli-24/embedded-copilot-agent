"""Typed, deep-copied v0.53-v0.56 input boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError, field_validator, model_validator

from embedded_copilot.engineering_artifacts import EngineeringArtifactContract
from embedded_copilot.engineering_execution import (
    EngineeringExecutionReport,
    EngineeringExecutionState,
)
from embedded_copilot.engineering_feedback import (
    EngineeringFeedbackReport,
    FeedbackItemType,
)
from embedded_copilot.engineering_optimization.models import (
    EngineeringOptimizationTarget,
    _OptimizationContract,
    _fingerprint,
    _fingerprint_value,
    _identifier,
    _tuple,
    _utc,
)
from embedded_copilot.engineering_validation import (
    HardwareValidationReport,
    ValidationAnalysisStatus,
)


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise ValueError("typed upstream contract is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)


class EngineeringOptimizationRequest(_OptimizationContract):
    request_id: str
    artifact_contract: EngineeringArtifactContract
    execution_report: EngineeringExecutionReport | None = None
    validation_report: HardwareValidationReport | None = None
    feedback_report: EngineeringFeedbackReport | None = None
    optimization_targets: tuple[EngineeringOptimizationTarget, ...]
    requested_at: datetime
    fingerprint: str

    _request_id = field_validator("request_id")(
        lambda value: _identifier(value, field="request_id")
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("artifact_contract", mode="before")
    @classmethod
    def validate_artifact_contract(cls, value: object) -> EngineeringArtifactContract:
        return _typed_copy(value, EngineeringArtifactContract)

    @field_validator("execution_report", mode="before")
    @classmethod
    def validate_execution_report(
        cls, value: object
    ) -> EngineeringExecutionReport | None:
        return None if value is None else _typed_copy(value, EngineeringExecutionReport)

    @field_validator("validation_report", mode="before")
    @classmethod
    def validate_validation_report(
        cls, value: object
    ) -> HardwareValidationReport | None:
        return None if value is None else _typed_copy(value, HardwareValidationReport)

    @field_validator("feedback_report", mode="before")
    @classmethod
    def validate_feedback_report(
        cls, value: object
    ) -> EngineeringFeedbackReport | None:
        return None if value is None else _typed_copy(value, EngineeringFeedbackReport)

    @field_validator("optimization_targets", mode="before")
    @classmethod
    def validate_targets_tuple(cls, value: object) -> object:
        return _tuple(value, field="optimization_targets")

    @model_validator(mode="after")
    def validate_request(self) -> EngineeringOptimizationRequest:
        keys = tuple(item.optimization_id for item in self.optimization_targets)
        if (
            not keys
            or len(keys) > 64
            or keys != tuple(sorted(keys))
            or len(keys) != len(set(keys))
        ):
            raise ValueError("optimization targets must be sorted and unique")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_optimization_request_fingerprint(**values):
            raise ValueError("optimization request fingerprint mismatch")
        return self


def engineering_optimization_request_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringOptimizationRequest", **values)


@dataclass(frozen=True, slots=True)
class _ProjectedOptimizationRequest:
    request: EngineeringOptimizationRequest
    execution_report_fingerprint: str | None
    validation_report_fingerprint: str | None
    feedback_report_fingerprint: str | None
    validation_issue: bool
    execution_issue: bool
    feedback_change_requested: bool


def project_request(value: object) -> _ProjectedOptimizationRequest:
    if type(value) is not EngineeringOptimizationRequest:
        raise TypeError("typed engineering optimization request is required")
    try:
        copied = value.model_copy(deep=True)
        checked = EngineeringOptimizationRequest.model_validate(copied)
        contract = checked.artifact_contract
        artifact_fingerprints = {
            item.artifact_fingerprint for item in contract.artifacts
        }
        if any(
            item.target_artifact_fingerprint not in artifact_fingerprints
            for item in checked.optimization_targets
        ):
            raise ValueError("optimization target binding is invalid")
        _validate_execution_binding(contract, checked.execution_report)
        _validate_validation_binding(contract, checked.validation_report)
        _validate_feedback_binding(contract, checked.feedback_report)
        if checked.feedback_report is not None:
            feedback = checked.feedback_report.feedback
            if feedback.execution_report_fingerprint is not None and (
                checked.execution_report is None
                or feedback.execution_report_fingerprint
                != checked.execution_report.fingerprint
            ):
                raise ValueError("feedback execution binding is invalid")
            if feedback.validation_report_fingerprint is not None and (
                checked.validation_report is None
                or feedback.validation_report_fingerprint
                != checked.validation_report.fingerprint
            ):
                raise ValueError("feedback validation binding is invalid")
    except (TypeError, ValueError, ValidationError):
        raise ValueError("optimization request is invalid") from None
    return _ProjectedOptimizationRequest(
        request=checked,
        execution_report_fingerprint=_optional_fingerprint(checked.execution_report),
        validation_report_fingerprint=_optional_fingerprint(checked.validation_report),
        feedback_report_fingerprint=_optional_fingerprint(checked.feedback_report),
        validation_issue=_has_validation_issue(checked.validation_report),
        execution_issue=_has_execution_issue(checked.execution_report),
        feedback_change_requested=_has_feedback_change(checked.feedback_report),
    )


def _validate_execution_binding(contract, report) -> None:
    if report is None:
        return
    if (
        report.artifact_fingerprint != contract.fingerprint
        or report.execution_contract.artifact_source_fingerprint
        != contract.artifact_source_fingerprint
    ):
        raise ValueError("execution report binding is invalid")


def _validate_validation_binding(contract, report) -> None:
    if report is None:
        return
    available = {
        source.source_fingerprint
        for binding in contract.source_bindings
        for source in binding.sources
    }
    required = {
        report.requirement_fingerprint,
        report.context_fingerprint,
        report.hardware_proposal_fingerprint,
        report.firmware_proposal_fingerprint,
    }
    if not required.issubset(available):
        raise ValueError("validation report binding is invalid")


def _validate_feedback_binding(contract, report) -> None:
    if report is None:
        return
    if (
        report.feedback.artifact_contract_fingerprint != contract.fingerprint
        or report.feedback.artifact_source_fingerprint
        != contract.artifact_source_fingerprint
    ):
        raise ValueError("feedback report binding is invalid")


def _optional_fingerprint(value) -> str | None:
    return None if value is None else value.fingerprint


def _has_validation_issue(report: HardwareValidationReport | None) -> bool:
    return report is not None and any(
        item.status
        in {
            ValidationAnalysisStatus.NOT_MET,
            ValidationAnalysisStatus.UNKNOWN,
            ValidationAnalysisStatus.CONFLICT,
        }
        for item in report.evidence_analysis.results
    )


def _has_execution_issue(report: EngineeringExecutionReport | None) -> bool:
    return report is not None and report.execution_status in {
        EngineeringExecutionState.FAILED,
        EngineeringExecutionState.BLOCKED,
    }


def _has_feedback_change(report: EngineeringFeedbackReport | None) -> bool:
    return report is not None and any(
        item.type is FeedbackItemType.REQUEST_CHANGE for item in report.feedback.items
    )


__all__ = (
    "EngineeringOptimizationRequest",
    "engineering_optimization_request_fingerprint",
)
