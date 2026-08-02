"""Immutable contracts for the v0.55 Engineering Execution Layer."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


class _ExecutionContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    checked = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(checked) is None:
        raise ValueError(f"{field} is invalid")
    return checked


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _identifiers(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_identifier(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _tokens(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_token(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(contract_kind: str, **values: object) -> str:
    encoded = json.dumps(
        _jsonable({"kind": contract_kind, **values}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class _Fingerprinted(_ExecutionContract):
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> _Fingerprinted:
        values = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "fingerprint"
        }
        if self.fingerprint != _fingerprint(type(self).__name__, **values):
            raise ValueError(f"{type(self).__name__} fingerprint mismatch")
        return self


def _model_fingerprint(model_type: type[_Fingerprinted], **values: object) -> str:
    return _fingerprint(model_type.__name__, **values)


class EngineeringExecutionType(StrEnum):
    BUILD = "BUILD"
    FLASH = "FLASH"
    DEBUG = "DEBUG"


class EngineeringExecutionState(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ExecutionPolicyStatus(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class ExecutionApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExecutionToolType(StrEnum):
    BUILD_ADAPTER = "BUILD_ADAPTER"
    FLASH_ADAPTER = "FLASH_ADAPTER"
    DEBUG_ADAPTER = "DEBUG_ADAPTER"


class ExecutionArtifactType(StrEnum):
    FIRMWARE_STRUCTURE = "FIRMWARE_STRUCTURE"
    HARDWARE_MODEL = "HARDWARE_MODEL"
    SCHEMATIC_INTENT = "SCHEMATIC_INTENT"
    PCB_CONSTRAINT = "PCB_CONSTRAINT"


class ExecutionArtifactStatus(StrEnum):
    GENERATED = "GENERATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class ExecutableArtifactStatus(StrEnum):
    AVAILABLE = "AVAILABLE"


class BuildResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class FlashResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class DebugResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class DebugDiagnosticType(StrEnum):
    COMPILE_ERROR = "COMPILE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    MEMORY_ISSUE = "MEMORY_ISSUE"


class ExecutionFindingCode(StrEnum):
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    ARTIFACT_UNAVAILABLE = "ARTIFACT_UNAVAILABLE"
    ARTIFACT_REVIEW_REQUIRED = "ARTIFACT_REVIEW_REQUIRED"
    EXECUTION_PORT_UNAVAILABLE = "EXECUTION_PORT_UNAVAILABLE"
    ADAPTER_BINDING_MISMATCH = "ADAPTER_BINDING_MISMATCH"
    PORT_RESULT_INVALID = "PORT_RESULT_INVALID"
    ARTIFACT_MUTATED = "ARTIFACT_MUTATED"
    BUILD_FAILED = "BUILD_FAILED"
    FLASH_FAILED = "FLASH_FAILED"
    DEBUG_FAILED = "DEBUG_FAILED"
    EXECUTABLE_ARTIFACT_UNAVAILABLE = "EXECUTABLE_ARTIFACT_UNAVAILABLE"


class ExecutionResultType(StrEnum):
    BUILD = "BUILD"
    FLASH = "FLASH"
    DEBUG = "DEBUG"
    BLOCKED = "BLOCKED"


class ExecutionAdapterMetadata(_Fingerprinted):
    binding_id: str
    execution_type: EngineeringExecutionType
    tool_type: ExecutionToolType

    _binding_id = field_validator("binding_id")(
        lambda value: _identifier(value, field="binding_id")
    )

    @model_validator(mode="after")
    def validate_tool_type(self) -> ExecutionAdapterMetadata:
        expected = {
            EngineeringExecutionType.BUILD: ExecutionToolType.BUILD_ADAPTER,
            EngineeringExecutionType.FLASH: ExecutionToolType.FLASH_ADAPTER,
            EngineeringExecutionType.DEBUG: ExecutionToolType.DEBUG_ADAPTER,
        }[self.execution_type]
        if self.tool_type is not expected:
            raise ValueError("adapter metadata type mismatch")
        return self


def execution_adapter_metadata_fingerprint(**values: object) -> str:
    return _fingerprint("ExecutionAdapterMetadata", **values)


class ExecutionPolicy(_Fingerprinted):
    policy_id: str
    execution_id: str
    artifact_contract_fingerprint: str
    artifact_source_fingerprint: str
    execution_type: EngineeringExecutionType
    execution_input_fingerprint: str
    adapter_binding_id: str
    status: ExecutionPolicyStatus

    @field_validator("policy_id", "execution_id", "adapter_binding_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _artifact_contract = field_validator("artifact_contract_fingerprint")(
        _fingerprint_value
    )
    _artifact_source = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )
    _execution_input = field_validator("execution_input_fingerprint")(
        _fingerprint_value
    )


def execution_policy_fingerprint(**values: object) -> str:
    return _fingerprint("ExecutionPolicy", **values)


class ExecutionApprovalContract(_Fingerprinted):
    execution_id: str
    artifact_contract_fingerprint: str
    artifact_source_fingerprint: str
    execution_type: EngineeringExecutionType
    execution_input_fingerprint: str
    execution_policy_fingerprint: str
    status: ExecutionApprovalStatus
    reviewer: str | None = None
    reviewed_at: datetime | None = None

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _artifact_contract = field_validator("artifact_contract_fingerprint")(
        _fingerprint_value
    )
    _artifact_source = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )
    _execution_input = field_validator("execution_input_fingerprint")(
        _fingerprint_value
    )
    _policy = field_validator("execution_policy_fingerprint")(_fingerprint_value)

    @field_validator("reviewer")
    @classmethod
    def validate_reviewer(cls, value: object) -> str | None:
        if value is None:
            return None
        return _identifier(value, field="reviewer")

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: object) -> datetime | None:
        if value is None:
            return None
        return _utc(value, field="reviewed_at")

    @model_validator(mode="after")
    def validate_review_binding(self) -> ExecutionApprovalContract:
        reviewed = self.reviewer is not None and self.reviewed_at is not None
        if self.status is ExecutionApprovalStatus.PENDING:
            if self.reviewer is not None or self.reviewed_at is not None:
                raise ValueError("pending approval cannot contain review proof")
        elif not reviewed:
            raise ValueError("review proof is required")
        return self


def execution_approval_fingerprint(**values: object) -> str:
    return _fingerprint("ExecutionApprovalContract", **values)


class ExecutableArtifactReference(_Fingerprinted):
    reference_id: str
    source_artifact_fingerprint: str
    artifact_fingerprint: str
    status: ExecutableArtifactStatus

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _source_fingerprint = field_validator("source_artifact_fingerprint")(
        _fingerprint_value
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)


def executable_artifact_reference_fingerprint(**values: object) -> str:
    return _fingerprint("ExecutableArtifactReference", **values)


class ExecutionArtifactBinding(_Fingerprinted):
    artifact_contract_fingerprint: str
    artifact_source_fingerprint: str
    artifact_type: ExecutionArtifactType
    artifact_status: ExecutionArtifactStatus
    artifact_fingerprint: str

    _contract_fingerprint = field_validator("artifact_contract_fingerprint")(
        _fingerprint_value
    )
    _source_fingerprint = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)


def execution_artifact_binding_fingerprint(**values: object) -> str:
    return _fingerprint("ExecutionArtifactBinding", **values)


class BuildResult(_Fingerprinted):
    result_type: Literal[ExecutionResultType.BUILD] = ExecutionResultType.BUILD
    artifact_fingerprint: str
    tool_type: ExecutionToolType
    status: BuildResultStatus
    finding_codes: tuple[str, ...]

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)
    _finding_codes = field_validator("finding_codes", mode="before")(
        lambda value: _tokens(value, field="finding_codes")
    )

    @model_validator(mode="after")
    def validate_tool(self) -> BuildResult:
        if self.tool_type is not ExecutionToolType.BUILD_ADAPTER:
            raise ValueError("build tool type mismatch")
        return self


def build_result_fingerprint(**values: object) -> str:
    values.setdefault("result_type", ExecutionResultType.BUILD)
    return _fingerprint("BuildResult", **values)


class FlashResult(_Fingerprinted):
    result_type: Literal[ExecutionResultType.FLASH] = ExecutionResultType.FLASH
    artifact_fingerprint: str
    tool_type: ExecutionToolType
    status: FlashResultStatus
    finding_codes: tuple[str, ...]

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)
    _finding_codes = field_validator("finding_codes", mode="before")(
        lambda value: _tokens(value, field="finding_codes")
    )

    @model_validator(mode="after")
    def validate_tool(self) -> FlashResult:
        if self.tool_type is not ExecutionToolType.FLASH_ADAPTER:
            raise ValueError("flash tool type mismatch")
        return self


def flash_result_fingerprint(**values: object) -> str:
    values.setdefault("result_type", ExecutionResultType.FLASH)
    return _fingerprint("FlashResult", **values)


class DebugRecommendationProjection(_Fingerprinted):
    recommendation_code: str
    evidence_reference_ids: tuple[str, ...]
    review_required: Literal[True] = True

    _recommendation_code = field_validator("recommendation_code")(
        lambda value: _token(value, field="recommendation_code")
    )
    _evidence_ids = field_validator("evidence_reference_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_reference_ids")
    )


def debug_recommendation_fingerprint(**values: object) -> str:
    values.setdefault("review_required", True)
    return _fingerprint("DebugRecommendationProjection", **values)


class DebugResult(_Fingerprinted):
    result_type: Literal[ExecutionResultType.DEBUG] = ExecutionResultType.DEBUG
    artifact_fingerprint: str
    tool_type: ExecutionToolType
    status: DebugResultStatus
    finding_codes: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]
    recommendations: tuple[DebugRecommendationProjection, ...]

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)
    _finding_codes = field_validator("finding_codes", mode="before")(
        lambda value: _tokens(value, field="finding_codes")
    )
    _evidence_ids = field_validator("evidence_reference_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_reference_ids")
    )

    @field_validator("recommendations", mode="before")
    @classmethod
    def validate_recommendations_tuple(cls, value: object) -> object:
        return _tuple(value, field="recommendations")

    @model_validator(mode="after")
    def validate_result(self) -> DebugResult:
        if self.tool_type is not ExecutionToolType.DEBUG_ADAPTER:
            raise ValueError("debug tool type mismatch")
        keys = tuple(item.recommendation_code for item in self.recommendations)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("recommendations must be sorted and unique")
        return self


def debug_result_fingerprint(**values: object) -> str:
    values.setdefault("result_type", ExecutionResultType.DEBUG)
    return _fingerprint("DebugResult", **values)


class ExecutionBlockedProjection(_Fingerprinted):
    result_type: Literal[ExecutionResultType.BLOCKED] = ExecutionResultType.BLOCKED
    execution_type: EngineeringExecutionType
    artifact_fingerprint: str
    finding_codes: tuple[ExecutionFindingCode, ...]

    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)

    @field_validator("finding_codes", mode="before")
    @classmethod
    def validate_findings(cls, value: object) -> object:
        return _tuple(value, field="finding_codes")


def execution_blocked_fingerprint(**values: object) -> str:
    values.setdefault("result_type", ExecutionResultType.BLOCKED)
    return _fingerprint("ExecutionBlockedProjection", **values)


class BuildRequest(_Fingerprinted):
    execution_id: str
    artifact: ExecutionArtifactBinding
    policy_fingerprint: str
    approval_fingerprint: str
    requested_at: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _policy = field_validator("policy_fingerprint")(_fingerprint_value)
    _approval = field_validator("approval_fingerprint")(_fingerprint_value)
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


class FlashRequest(_Fingerprinted):
    execution_id: str
    artifact: ExecutionArtifactBinding
    executable_artifact: ExecutableArtifactReference
    policy_fingerprint: str
    approval_fingerprint: str
    requested_at: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _policy = field_validator("policy_fingerprint")(_fingerprint_value)
    _approval = field_validator("approval_fingerprint")(_fingerprint_value)
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


class DebugRequest(_Fingerprinted):
    execution_id: str
    artifact: ExecutionArtifactBinding
    build_result: BuildResult
    validation_report_fingerprint: str
    validation_finding_codes: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]
    diagnostic_types: tuple[DebugDiagnosticType, ...]
    policy_fingerprint: str
    approval_fingerprint: str
    requested_at: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _validation_fingerprint = field_validator("validation_report_fingerprint")(
        _fingerprint_value
    )
    _validation_findings = field_validator("validation_finding_codes", mode="before")(
        lambda value: _tokens(value, field="validation_finding_codes")
    )
    _evidence_ids = field_validator("evidence_reference_ids", mode="before")(
        lambda value: _identifiers(value, field="evidence_reference_ids")
    )
    _policy = field_validator("policy_fingerprint")(_fingerprint_value)
    _approval = field_validator("approval_fingerprint")(_fingerprint_value)
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )

    @field_validator("diagnostic_types", mode="before")
    @classmethod
    def validate_diagnostic_tuple(cls, value: object) -> object:
        return _tuple(value, field="diagnostic_types")

    @model_validator(mode="after")
    def validate_diagnostic_order(self) -> DebugRequest:
        order = {value: index for index, value in enumerate(DebugDiagnosticType)}
        keys = tuple(order[item] for item in self.diagnostic_types)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("diagnostic types must be sorted and unique")
        return self


def port_request_fingerprint(model_type: type[_Fingerprinted], **values: object) -> str:
    return _model_fingerprint(model_type, **values)


class EngineeringExecutionContract(_Fingerprinted):
    execution_id: str
    artifact_fingerprint: str
    artifact_source_fingerprint: str
    execution_type: EngineeringExecutionType
    execution_input_fingerprint: str
    policy_fingerprint: str
    approval_fingerprint: str
    adapter_binding_id: str
    approval_required: Literal[True] = True
    execution_state: EngineeringExecutionState

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)
    _source_fingerprint = field_validator("artifact_source_fingerprint")(
        _fingerprint_value
    )
    _input_fingerprint = field_validator("execution_input_fingerprint")(
        _fingerprint_value
    )
    _policy_fingerprint = field_validator("policy_fingerprint")(_fingerprint_value)
    _approval_fingerprint = field_validator("approval_fingerprint")(_fingerprint_value)
    _adapter_binding_id = field_validator("adapter_binding_id")(
        lambda value: _identifier(value, field="adapter_binding_id")
    )


class ExecutionReviewProjection(_Fingerprinted):
    execution_id: str
    approval_status: ExecutionApprovalStatus
    policy_status: ExecutionPolicyStatus
    artifact_review_required: bool
    adapter_called: bool
    finding_codes: tuple[ExecutionFindingCode, ...]
    state_history: tuple[EngineeringExecutionState, ...]
    review_required: Literal[True] = True

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )

    @field_validator("finding_codes", "state_history", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_review(self) -> ExecutionReviewProjection:
        finding_order = {
            value: index for index, value in enumerate(ExecutionFindingCode)
        }
        finding_keys = tuple(finding_order[item] for item in self.finding_codes)
        if finding_keys != tuple(sorted(finding_keys)) or len(finding_keys) != len(
            set(finding_keys)
        ):
            raise ValueError("finding codes must be sorted and unique")
        allowed = {
            (
                EngineeringExecutionState.PROPOSED,
                EngineeringExecutionState.BLOCKED,
            ),
            (
                EngineeringExecutionState.PROPOSED,
                EngineeringExecutionState.APPROVED,
                EngineeringExecutionState.EXECUTED,
            ),
            (
                EngineeringExecutionState.PROPOSED,
                EngineeringExecutionState.APPROVED,
                EngineeringExecutionState.FAILED,
            ),
            (
                EngineeringExecutionState.PROPOSED,
                EngineeringExecutionState.APPROVED,
                EngineeringExecutionState.BLOCKED,
            ),
        }
        if self.state_history not in allowed:
            raise ValueError("state history is invalid")
        return self


def engineering_execution_report_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("EngineeringExecutionReport", **values)


class EngineeringExecutionReport(_ExecutionContract):
    schema_version: Literal["1.0"] = "1.0"
    execution_id: str
    execution_contract: EngineeringExecutionContract
    execution_status: EngineeringExecutionState
    artifact_fingerprint: str
    approval_fingerprint: str
    result: BuildResult | FlashResult | DebugResult | ExecutionBlockedProjection
    review: ExecutionReviewProjection
    requested_at: datetime
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(_fingerprint_value)
    _approval_fingerprint = field_validator("approval_fingerprint")(_fingerprint_value)
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_report(self) -> EngineeringExecutionReport:
        if (
            self.execution_contract.execution_id != self.execution_id
            or self.execution_contract.execution_state is not self.execution_status
            or self.execution_contract.artifact_fingerprint != self.artifact_fingerprint
            or self.execution_contract.approval_fingerprint != self.approval_fingerprint
            or self.review.execution_id != self.execution_id
            or self.review.state_history[-1] is not self.execution_status
        ):
            raise ValueError("execution report binding mismatch")
        expected = engineering_execution_report_fingerprint(
            execution_id=self.execution_id,
            execution_contract=self.execution_contract,
            execution_status=self.execution_status,
            artifact_fingerprint=self.artifact_fingerprint,
            approval_fingerprint=self.approval_fingerprint,
            result=self.result,
            review=self.review,
            requested_at=self.requested_at,
            candidate_semantics=self.candidate_semantics,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("engineering execution report fingerprint mismatch")
        return self
