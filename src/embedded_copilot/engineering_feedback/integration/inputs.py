"""Typed, deep-copied v0.53-v0.55 input boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError, field_validator, model_validator

from embedded_copilot.engineering_artifacts import (
    ArtifactType,
    EngineeringArtifactContract,
)
from embedded_copilot.engineering_execution import EngineeringExecutionReport
from embedded_copilot.engineering_feedback.models import (
    FeedbackItem,
    FeedbackItemType,
    FeedbackTargetDomain,
    RequestChangeFeedbackItem,
    _FeedbackContract,
    _fingerprint,
    _fingerprint_value,
    _identifier,
    _tuple,
    _utc,
)
from embedded_copilot.engineering_validation import HardwareValidationReport


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise ValueError("typed upstream contract is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)


class EngineeringFeedbackRequest(_FeedbackContract):
    feedback_id: str
    artifact_contract: EngineeringArtifactContract
    execution_report: EngineeringExecutionReport | None = None
    validation_report: HardwareValidationReport | None = None
    feedback_items: tuple[FeedbackItem, ...]
    submitted_at: datetime
    fingerprint: str

    _feedback_id = field_validator("feedback_id")(
        lambda value: _identifier(value, field="feedback_id")
    )
    _submitted_at = field_validator("submitted_at")(
        lambda value: _utc(value, field="submitted_at")
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
        if value is None:
            return None
        return _typed_copy(value, EngineeringExecutionReport)

    @field_validator("validation_report", mode="before")
    @classmethod
    def validate_validation_report(
        cls, value: object
    ) -> HardwareValidationReport | None:
        if value is None:
            return None
        return _typed_copy(value, HardwareValidationReport)

    @field_validator("feedback_items", mode="before")
    @classmethod
    def validate_items_tuple(cls, value: object) -> object:
        return _tuple(value, field="feedback_items")

    @model_validator(mode="after")
    def validate_request(self) -> EngineeringFeedbackRequest:
        if not self.feedback_items or len(self.feedback_items) > 64:
            raise ValueError("feedback items capacity is invalid")
        item_types = {item.type for item in self.feedback_items}
        if len(item_types) != 1:
            raise ValueError("feedback items must use one type")
        keys = tuple(_item_key(item) for item in self.feedback_items)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("feedback items must be sorted and unique")
        if next(iter(item_types)) is FeedbackItemType.REQUEST_CHANGE:
            change_ids = tuple(item.change_id for item in self.feedback_items)
            revision_ids = tuple(item.revision_id for item in self.feedback_items)
            if len(change_ids) != len(set(change_ids)) or len(revision_ids) != len(
                set(revision_ids)
            ):
                raise ValueError("change and revision IDs must be unique")
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != engineering_feedback_request_fingerprint(**values):
            raise ValueError("feedback request fingerprint mismatch")
        return self


def _item_key(item) -> tuple[str, ...]:
    if isinstance(item, RequestChangeFeedbackItem):
        return (item.change_id, item.revision_id, item.target_reference, item.reason)
    return (item.target_reference, item.reason, item.fingerprint)


def engineering_feedback_request_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringFeedbackRequest", **values)


@dataclass(frozen=True, slots=True)
class _ProjectedFeedbackRequest:
    request: EngineeringFeedbackRequest
    execution_report_fingerprint: str | None
    validation_report_fingerprint: str | None


def project_request(value: object) -> _ProjectedFeedbackRequest:
    if type(value) is not EngineeringFeedbackRequest:
        raise TypeError("typed engineering feedback request is required")
    try:
        copied = value.model_copy(deep=True)
        checked = EngineeringFeedbackRequest.model_validate(copied)
    except (TypeError, ValueError, ValidationError):
        raise ValueError("feedback request is invalid") from None
    contract = checked.artifact_contract
    entries = {
        item.artifact_fingerprint: item.artifact_type for item in contract.artifacts
    }
    all_targets = set(entries) | {contract.fingerprint}
    for item in checked.feedback_items:
        if item.target_reference not in all_targets:
            raise ValueError("feedback target binding is invalid")
        if isinstance(item, RequestChangeFeedbackItem):
            if item.target_reference not in entries:
                raise ValueError("change target binding is invalid")
            artifact_type = entries[item.target_reference]
            if item.target_domain is FeedbackTargetDomain.FIRMWARE and (
                artifact_type is not ArtifactType.FIRMWARE_STRUCTURE
            ):
                raise ValueError("firmware change target is invalid")
            if item.target_domain is FeedbackTargetDomain.HARDWARE and (
                artifact_type is ArtifactType.FIRMWARE_STRUCTURE
            ):
                raise ValueError("hardware change target is invalid")
    execution_fingerprint = None
    if checked.execution_report is not None:
        execution = checked.execution_report
        if (
            execution.artifact_fingerprint != contract.fingerprint
            or execution.execution_contract.artifact_source_fingerprint
            != contract.artifact_source_fingerprint
        ):
            raise ValueError("execution report binding is invalid")
        execution_fingerprint = execution.fingerprint
    validation_fingerprint = None
    if checked.validation_report is not None:
        validation = checked.validation_report
        source_fingerprints = {
            source.source_fingerprint
            for binding in contract.source_bindings
            for source in binding.sources
        }
        required = {
            validation.requirement_fingerprint,
            validation.context_fingerprint,
            validation.hardware_proposal_fingerprint,
            validation.firmware_proposal_fingerprint,
        }
        if not required.issubset(source_fingerprints):
            raise ValueError("validation report binding is invalid")
        validation_fingerprint = validation.fingerprint
    return _ProjectedFeedbackRequest(
        request=checked,
        execution_report_fingerprint=execution_fingerprint,
        validation_report_fingerprint=validation_fingerprint,
    )


__all__ = (
    "EngineeringFeedbackRequest",
    "engineering_feedback_request_fingerprint",
)
