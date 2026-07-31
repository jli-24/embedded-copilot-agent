"""Immutable contracts for the Engineering Generation Runtime."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$"
_TOKEN = r"^[A-Z0-9][A-Z0-9_]{1,63}$"
_METRIC_NAME = r"^[a-z][a-z0-9_]{0,63}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"
_SENSITIVE = (
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])"
)
_ABSOLUTE_PATH = r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)"


class _GenerationContract(BaseModel):
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
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > maximum
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or re.search(_SENSITIVE, candidate, re.IGNORECASE) is not None
        or re.search(_ABSOLUTE_PATH, candidate) is not None
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or re.fullmatch(_TOKEN, value) is None:
        raise ValueError(f"{field} is invalid")
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


def _safe_text_tuple(
    value: object, *, field: str, allow_empty: bool = True
) -> tuple[str, ...]:
    items = _tuple(value, field=field)
    checked = tuple(_safe_text(item, field=field, maximum=512) for item in items)
    if not allow_empty and not checked:
        raise ValueError(f"{field} must not be empty")
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _token_tuple(
    value: object, *, field: str, allow_empty: bool = True
) -> tuple[str, ...]:
    items = _tuple(value, field=field)
    checked = tuple(_token(item, field=field) for item in items)
    if not allow_empty and not checked:
        raise ValueError(f"{field} must not be empty")
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or re.fullmatch(_FINGERPRINT, value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _finite(value: object, *, field: str, minimum: float = 0.0) -> float:
    if type(value) not in (int, float) or type(value) is bool:
        raise ValueError(f"{field} is invalid")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{field} is invalid")
    return result


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


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class GeneratorType(StrEnum):
    HARDWARE_DESIGN = "HARDWARE_DESIGN"
    FIRMWARE = "FIRMWARE"
    PCB_DESIGN = "PCB_DESIGN"
    BOM = "BOM"


class ArtifactType(StrEnum):
    HARDWARE_DESIGN = "HARDWARE_DESIGN"
    FIRMWARE = "FIRMWARE"
    PCB_DESIGN = "PCB_DESIGN"
    BOM = "BOM"


class GenerationReferenceType(StrEnum):
    DATASHEET_REFERENCE = "DATASHEET_REFERENCE"
    COMPONENT_REFERENCE = "COMPONENT_REFERENCE"
    DESIGN_REFERENCE = "DESIGN_REFERENCE"


class ArtifactLifecycleState(StrEnum):
    CREATED = "CREATED"
    GENERATING = "GENERATING"
    VERIFYING = "VERIFYING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class GenerationFailureCode(StrEnum):
    GENERATOR_UNAVAILABLE = "generator_unavailable"
    GENERATION_TIMEOUT = "generation_timeout"
    PROPOSAL_REJECTED = "proposal_rejected"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    VERIFICATION_INVALID = "verification_invalid"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_UNAVAILABLE = "approval_unavailable"


class GenerationVerificationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class ArtifactApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class GenerationApprovalStatus(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class GenerationMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    MILLISECONDS = "milliseconds"


class GenerationContextReference(_GenerationContract):
    reference_type: GenerationReferenceType
    reference_id: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )


class GenerationContextProjection(_GenerationContract):
    summary: str
    references: tuple[GenerationContextReference, ...]
    verified_source_references: tuple[GenerationContextReference, ...]

    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )

    @field_validator("references", "verified_source_references", mode="before")
    @classmethod
    def _reference_tuples(cls, value: object) -> object:
        return _tuple(value, field="references")

    @field_validator("references", "verified_source_references")
    @classmethod
    def _references_sorted(
        cls, value: tuple[GenerationContextReference, ...]
    ) -> tuple[GenerationContextReference, ...]:
        keys = tuple((item.reference_type.value, item.reference_id) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("references must be sorted and unique")
        return value


class ArtifactGenerationRequest(_GenerationContract):
    generation_id: str
    workflow_id: str
    task_id: str
    artifact_type: ArtifactType
    input_context: GenerationContextProjection
    constraints: tuple[str, ...]
    timestamp: datetime

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("constraints", mode="before")
    @classmethod
    def _constraints(cls, value: object) -> tuple[str, ...]:
        return _safe_text_tuple(value, field="constraints")


class GeneratorResolutionRequest(_GenerationContract):
    generation_id: str
    generator_type: GeneratorType

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )


def generator_binding_fingerprint(
    *, generator_type: GeneratorType, capabilities: tuple[str, ...]
) -> str:
    return _fingerprint(
        {"generator_type": generator_type, "capabilities": capabilities}
    )


class GeneratorBindingMetadata(_GenerationContract):
    generator_type: GeneratorType
    capabilities: tuple[str, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _capabilities(cls, value: object) -> tuple[str, ...]:
        return _token_tuple(value, field="capabilities", allow_empty=False)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> GeneratorBindingMetadata:
        expected = generator_binding_fingerprint(
            generator_type=self.generator_type,
            capabilities=self.capabilities,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint mismatch")
        return self


class GeneratorInvocationRequest(_GenerationContract):
    request: ArtifactGenerationRequest


class HardwareDesignStructuredOutput(_GenerationContract):
    mcu: str
    peripherals: tuple[str, ...]
    communications: tuple[str, ...]
    power_architecture: str

    _mcu = field_validator("mcu")(
        lambda value: _safe_text(value, field="mcu", maximum=128)
    )
    _power = field_validator("power_architecture")(
        lambda value: _safe_text(value, field="power_architecture", maximum=128)
    )

    @field_validator("peripherals", "communications", mode="before")
    @classmethod
    def _labels(cls, value: object) -> tuple[str, ...]:
        return _safe_text_tuple(value, field="structured_output")


class FirmwareStructuredOutput(_GenerationContract):
    project_structure: tuple[str, ...]
    bsp: tuple[str, ...]
    drivers: tuple[str, ...]
    middleware: tuple[str, ...]
    application: tuple[str, ...]
    freertos_tasks: tuple[str, ...]

    @field_validator(
        "project_structure",
        "bsp",
        "drivers",
        "middleware",
        "application",
        "freertos_tasks",
        mode="before",
    )
    @classmethod
    def _labels(cls, value: object) -> tuple[str, ...]:
        return _safe_text_tuple(value, field="structured_output")


class PCBDesignStructuredOutput(_GenerationContract):
    placement_rules: tuple[str, ...]
    routing_constraints: tuple[str, ...]
    layer_suggestion: str

    @field_validator("placement_rules", "routing_constraints", mode="before")
    @classmethod
    def _rules(cls, value: object) -> tuple[str, ...]:
        return _safe_text_tuple(value, field="structured_output")

    _layer = field_validator("layer_suggestion")(
        lambda value: _safe_text(value, field="layer_suggestion", maximum=256)
    )


class BOMItem(_GenerationContract):
    component: str
    alternative: str
    cost: float
    supply_risk: Literal["LOW", "MEDIUM", "HIGH", "UNKNOWN"]

    _component = field_validator("component")(
        lambda value: _safe_text(value, field="component", maximum=128)
    )
    _alternative = field_validator("alternative")(
        lambda value: _safe_text(value, field="alternative", maximum=128)
    )
    _cost = field_validator("cost")(lambda value: _finite(value, field="cost"))


class BOMStructuredOutput(_GenerationContract):
    items: tuple[BOMItem, ...]

    @field_validator("items", mode="before")
    @classmethod
    def _items_tuple(cls, value: object) -> object:
        return _tuple(value, field="items")

    @field_validator("items")
    @classmethod
    def _items_unique(cls, value: tuple[BOMItem, ...]) -> tuple[BOMItem, ...]:
        keys = tuple(item.component for item in value)
        if not value or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("items must be sorted and unique")
        return value


StructuredArtifactOutput = (
    HardwareDesignStructuredOutput
    | FirmwareStructuredOutput
    | PCBDesignStructuredOutput
    | BOMStructuredOutput
)


class GenerationMetric(_GenerationContract):
    name: str
    value: float
    unit: GenerationMetricUnit

    @field_validator("name")
    @classmethod
    def _name(cls, value: object) -> str:
        if type(value) is not str or re.fullmatch(_METRIC_NAME, value) is None:
            raise ValueError("metric name is invalid")
        return value

    _value = field_validator("value")(
        lambda value: _finite(value, field="metric", minimum=0.0)
    )


def artifact_proposal_fingerprint(
    *,
    generation_id: str,
    workflow_id: str,
    task_id: str,
    artifact_type: ArtifactType,
    summary: str,
    structured_output: StructuredArtifactOutput,
    references: tuple[GenerationContextReference, ...],
    metrics: tuple[GenerationMetric, ...],
) -> str:
    return _fingerprint(
        {
            "generation_id": generation_id,
            "workflow_id": workflow_id,
            "task_id": task_id,
            "artifact_type": artifact_type,
            "summary": summary,
            "structured_output": structured_output,
            "references": references,
            "metrics": metrics,
        }
    )


class ArtifactProposal(_GenerationContract):
    generation_id: str
    workflow_id: str
    task_id: str
    artifact_type: ArtifactType
    summary: str
    structured_output: StructuredArtifactOutput
    references: tuple[GenerationContextReference, ...]
    metrics: tuple[GenerationMetric, ...]
    fingerprint: str

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("references", "metrics", mode="before")
    @classmethod
    def _tuples(cls, value: object) -> object:
        return _tuple(value, field="proposal collection")

    @field_validator("references")
    @classmethod
    def _references_unique(
        cls, value: tuple[GenerationContextReference, ...]
    ) -> tuple[GenerationContextReference, ...]:
        keys = tuple((item.reference_type.value, item.reference_id) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("references must be sorted and unique")
        return value

    @field_validator("metrics")
    @classmethod
    def _metrics_unique(
        cls, value: tuple[GenerationMetric, ...]
    ) -> tuple[GenerationMetric, ...]:
        keys = tuple(item.name for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("metrics must be sorted and unique")
        return value

    @model_validator(mode="after")
    def _proposal_matches(self) -> ArtifactProposal:
        expected_type = {
            ArtifactType.HARDWARE_DESIGN: HardwareDesignStructuredOutput,
            ArtifactType.FIRMWARE: FirmwareStructuredOutput,
            ArtifactType.PCB_DESIGN: PCBDesignStructuredOutput,
            ArtifactType.BOM: BOMStructuredOutput,
        }[self.artifact_type]
        if type(self.structured_output) is not expected_type:
            raise ValueError("structured output type mismatch")
        expected = artifact_proposal_fingerprint(
            generation_id=self.generation_id,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            artifact_type=self.artifact_type,
            summary=self.summary,
            structured_output=self.structured_output,
            references=self.references,
            metrics=self.metrics,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint mismatch")
        return self


class GenerationVerificationRequest(_GenerationContract):
    generation_id: str
    proposal: ArtifactProposal
    timestamp: datetime

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def generation_verification_result_fingerprint(
    *,
    generation_id: str,
    proposal_fingerprint: str,
    status: GenerationVerificationStatus,
) -> str:
    return _fingerprint(
        {
            "generation_id": generation_id,
            "proposal_fingerprint": proposal_fingerprint,
            "status": status,
        }
    )


class GenerationVerificationResult(_GenerationContract):
    generation_id: str
    proposal_fingerprint: str
    status: GenerationVerificationStatus
    fingerprint: str

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> GenerationVerificationResult:
        if self.fingerprint != generation_verification_result_fingerprint(
            generation_id=self.generation_id,
            proposal_fingerprint=self.proposal_fingerprint,
            status=self.status,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class ArtifactApprovalContext(_GenerationContract):
    generation_id: str
    artifact_fingerprint: str
    workflow_id: str
    decision: ArtifactApprovalDecision
    reviewer: str
    timestamp: datetime

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(
        _checked_fingerprint
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


class GenerationApprovalPolicyRequest(_GenerationContract):
    generation_id: str
    artifact_fingerprint: str
    workflow_id: str
    reviewer: str
    timestamp: datetime

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(
        _checked_fingerprint
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def generation_approval_policy_result_fingerprint(
    *,
    generation_id: str,
    artifact_fingerprint: str,
    status: GenerationApprovalStatus,
) -> str:
    return _fingerprint(
        {
            "generation_id": generation_id,
            "artifact_fingerprint": artifact_fingerprint,
            "status": status,
        }
    )


class GenerationApprovalPolicyResult(_GenerationContract):
    generation_id: str
    artifact_fingerprint: str
    status: GenerationApprovalStatus
    fingerprint: str

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _artifact_fingerprint = field_validator("artifact_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> GenerationApprovalPolicyResult:
        if self.fingerprint != generation_approval_policy_result_fingerprint(
            generation_id=self.generation_id,
            artifact_fingerprint=self.artifact_fingerprint,
            status=self.status,
        ):
            raise ValueError("fingerprint mismatch")
        return self


class ApprovedArtifactReference(_GenerationContract):
    generation_id: str
    artifact_type: ArtifactType
    proposal_fingerprint: str

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )


class GenerationProgressEvent(_GenerationContract):
    sequence: int
    generation_id: str
    workflow_id: str
    state: ArtifactLifecycleState
    timestamp: datetime

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("sequence")
    @classmethod
    def _sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("sequence is invalid")
        return value


def artifact_generation_snapshot_fingerprint(
    *,
    request: ArtifactGenerationRequest,
    state: ArtifactLifecycleState,
    proposal: ArtifactProposal | None,
    approved_artifact: ApprovedArtifactReference | None,
    failure_code: GenerationFailureCode | None,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "request": request,
            "state": state,
            "proposal": proposal,
            "approved_artifact": approved_artifact,
            "failure_code": failure_code,
            "progress_sequence": progress_sequence,
        }
    )


class ArtifactGenerationSnapshot(_GenerationContract):
    generation_id: str
    workflow_id: str
    task_id: str
    artifact_type: ArtifactType
    request: ArtifactGenerationRequest
    state: ArtifactLifecycleState
    proposal: ArtifactProposal | None = None
    approved_artifact: ApprovedArtifactReference | None = None
    failure_code: GenerationFailureCode | None = None
    progress_sequence: int
    fingerprint: str

    _generation_id = field_validator("generation_id")(
        lambda value: _identifier(value, field="generation_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("progress_sequence")
    @classmethod
    def _progress_sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress sequence is invalid")
        return value

    @model_validator(mode="after")
    def _snapshot_matches(self) -> ArtifactGenerationSnapshot:
        if (
            self.generation_id != self.request.generation_id
            or self.workflow_id != self.request.workflow_id
            or self.task_id != self.request.task_id
            or self.artifact_type is not self.request.artifact_type
        ):
            raise ValueError("snapshot binding mismatch")
        if self.proposal is not None and (
            self.proposal.generation_id != self.generation_id
            or self.proposal.workflow_id != self.workflow_id
            or self.proposal.task_id != self.task_id
            or self.proposal.artifact_type is not self.artifact_type
        ):
            raise ValueError("proposal binding mismatch")
        if (
            self.state is ArtifactLifecycleState.WAITING_APPROVAL
            and self.proposal is None
        ):
            raise ValueError("waiting snapshot requires proposal")
        if self.state is ArtifactLifecycleState.COMPLETED and (
            self.proposal is None or self.approved_artifact is None
        ):
            raise ValueError("completed snapshot requires approved artifact")
        expected = artifact_generation_snapshot_fingerprint(
            request=self.request,
            state=self.state,
            proposal=self.proposal,
            approved_artifact=self.approved_artifact,
            failure_code=self.failure_code,
            progress_sequence=self.progress_sequence,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint mismatch")
        return self
