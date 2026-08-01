"""Immutable public contracts for the Execution Integration Runtime."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$"
_TYPE_TOKEN = r"^[A-Z][A-Z0-9_]{2,63}$"
_METRIC_NAME = r"^[a-z][a-z0-9_]{0,63}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"
_SENSITIVE = (
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])"
)
_ABSOLUTE_PATH = r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)"


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
    candidate = unicodedata.normalize("NFC", value.strip())
    if re.fullmatch(_IDENTIFIER, candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _type_token(value: object, *, field: str) -> str:
    if type(value) is not str or re.fullmatch(_TYPE_TOKEN, value) is None:
        raise ValueError(f"{field} is invalid")
    return value


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


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or re.fullmatch(_FINGERPRINT, value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class ExecutorType(StrEnum):
    BUILD = "BUILD"
    FLASH = "FLASH"
    DEBUG = "DEBUG"
    VERIFY = "VERIFY"


class ExecutionState(StrEnum):
    CREATED = "CREATED"
    READY = "READY"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class ExecutionResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ExecutionVerificationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class ExecutionFailureCode(StrEnum):
    EXECUTOR_UNAVAILABLE = "executor_unavailable"
    EXECUTOR_REJECTED = "executor_rejected"
    EXECUTOR_FAILED = "executor_failed"
    EXECUTOR_TIMEOUT = "executor_timeout"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    VERIFICATION_INVALID = "verification_invalid"
    APPROVAL_DENIED = "approval_denied"
    REVISION_REQUIRED = "revision_required"


class ExecutionProgressEventType(StrEnum):
    EXECUTION_CREATED = "EXECUTION_CREATED"
    EXECUTION_READY = "EXECUTION_READY"
    EXECUTION_APPROVED = "EXECUTION_APPROVED"
    EXECUTION_RUNNING = "EXECUTION_RUNNING"
    EXECUTION_VERIFYING = "EXECUTION_VERIFYING"
    EXECUTION_SUCCEEDED = "EXECUTION_SUCCEEDED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_TIMED_OUT = "EXECUTION_TIMED_OUT"
    EXECUTION_CANCELLED = "EXECUTION_CANCELLED"


class ExecutionMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"


def execution_context_fingerprint(
    *, context_id: str, summary: str, reference_ids: tuple[str, ...]
) -> str:
    return _fingerprint(
        {
            "context_id": context_id,
            "reference_ids": list(reference_ids),
            "summary": summary,
        }
    )


class ExecutionContextProjection(_ExecutionContract):
    context_id: str
    summary: str
    reference_ids: tuple[str, ...]
    fingerprint: str

    _context_id = field_validator("context_id")(
        lambda value: _identifier(value, field="context_id")
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def _reference_tuple(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @field_validator("reference_ids")
    @classmethod
    def _references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_identifier(item, field="reference_id") for item in value)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("reference_ids must be sorted and unique")
        return checked

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ExecutionContextProjection:
        expected = execution_context_fingerprint(
            context_id=self.context_id,
            summary=self.summary,
            reference_ids=self.reference_ids,
        )
        if self.fingerprint != expected:
            raise ValueError("context fingerprint mismatch")
        return self


class ExecutionProposalReference(_ExecutionContract):
    proposal_id: str
    proposal_fingerprint: str

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )


class ExecutionPreparationRequest(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    executor_type: ExecutorType
    context: ExecutionContextProjection
    proposal: ExecutionProposalReference
    timestamp: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _agent_type = field_validator("agent_type")(
        lambda value: _type_token(value, field="agent_type")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def execution_plan_fingerprint(
    *,
    execution_id: str,
    workflow_id: str,
    task_id: str,
    agent_type: str,
    executor_type: ExecutorType,
    context: ExecutionContextProjection,
    proposal: ExecutionProposalReference,
    prepared_at: datetime,
) -> str:
    return _fingerprint(
        {
            "agent_type": agent_type,
            "context": context.model_dump(mode="json"),
            "execution_id": execution_id,
            "executor_type": executor_type.value,
            "prepared_at": prepared_at.isoformat(),
            "proposal": proposal.model_dump(mode="json"),
            "task_id": task_id,
            "workflow_id": workflow_id,
        }
    )


class ExecutionPlan(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    executor_type: ExecutorType
    context: ExecutionContextProjection
    proposal: ExecutionProposalReference
    prepared_at: datetime
    fingerprint: str

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _agent_type = field_validator("agent_type")(
        lambda value: _type_token(value, field="agent_type")
    )
    _prepared_at = field_validator("prepared_at")(
        lambda value: _utc(value, field="prepared_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ExecutionPlan:
        expected = execution_plan_fingerprint(
            execution_id=self.execution_id,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            agent_type=self.agent_type,
            executor_type=self.executor_type,
            context=self.context,
            proposal=self.proposal,
            prepared_at=self.prepared_at,
        )
        if self.fingerprint != expected:
            raise ValueError("plan fingerprint mismatch")
        return self


def execution_executor_metadata_fingerprint(
    *,
    binding_id: str,
    executor_type: ExecutorType,
    capabilities: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "binding_id": binding_id,
            "capabilities": list(capabilities),
            "executor_type": executor_type.value,
        }
    )


class ExecutionExecutorMetadata(_ExecutionContract):
    binding_id: str
    executor_type: ExecutorType
    capabilities: tuple[str, ...]
    fingerprint: str

    _binding_id = field_validator("binding_id")(
        lambda value: _identifier(value, field="binding_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _capability_tuple(cls, value: object) -> object:
        return _tuple(value, field="capabilities")

    @field_validator("capabilities")
    @classmethod
    def _capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_type_token(item, field="capability") for item in value)
        if (
            not checked
            or checked != tuple(sorted(checked))
            or len(checked) != len(set(checked))
        ):
            raise ValueError("capabilities must be sorted and unique")
        return checked

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ExecutionExecutorMetadata:
        if self.fingerprint != execution_executor_metadata_fingerprint(
            binding_id=self.binding_id,
            executor_type=self.executor_type,
            capabilities=self.capabilities,
        ):
            raise ValueError("executor metadata fingerprint mismatch")
        return self


class ExecutionExecutorResolutionRequest(_ExecutionContract):
    execution_id: str
    executor_type: ExecutorType

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )


class ExecutionArtifactReference(_ExecutionContract):
    reference_id: str
    artifact_type: str
    status: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _artifact_type = field_validator("artifact_type")(
        lambda value: _type_token(value, field="artifact_type")
    )
    _status = field_validator("status")(
        lambda value: _type_token(value, field="status")
    )


class ExecutionMetric(_ExecutionContract):
    name: str
    value: int | float
    unit: ExecutionMetricUnit

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if type(value) is not str or re.fullmatch(_METRIC_NAME, value) is None:
            raise ValueError("metric name is invalid")
        return value

    @field_validator("value")
    @classmethod
    def _value(cls, value: int | float) -> int | float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("metric value is invalid")
        return value


def execution_result_fingerprint(
    *,
    status: ExecutionResultStatus,
    summary: str,
    artifacts: tuple[ExecutionArtifactReference, ...],
    metrics: tuple[ExecutionMetric, ...],
) -> str:
    return _fingerprint(
        {
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
            "metrics": [item.model_dump(mode="json") for item in metrics],
            "status": status.value,
            "summary": summary,
        }
    )


class ExecutionResultProjection(_ExecutionContract):
    status: ExecutionResultStatus
    summary: str
    artifacts: tuple[ExecutionArtifactReference, ...]
    metrics: tuple[ExecutionMetric, ...]
    fingerprint: str

    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("artifacts", "metrics", mode="before")
    @classmethod
    def _collection_tuple(cls, value: object) -> object:
        return _tuple(value, field="collection")

    @model_validator(mode="after")
    def _collections_and_fingerprint(self) -> ExecutionResultProjection:
        artifact_keys = tuple(
            (item.artifact_type, item.reference_id, item.status)
            for item in self.artifacts
        )
        metric_keys = tuple(item.name for item in self.metrics)
        if artifact_keys != tuple(sorted(artifact_keys)) or len(artifact_keys) != len(
            set(artifact_keys)
        ):
            raise ValueError("artifacts must be sorted and unique")
        if metric_keys != tuple(sorted(metric_keys)) or len(metric_keys) != len(
            set(metric_keys)
        ):
            raise ValueError("metrics must be sorted and unique")
        expected = execution_result_fingerprint(
            status=self.status,
            summary=self.summary,
            artifacts=self.artifacts,
            metrics=self.metrics,
        )
        if self.fingerprint != expected:
            raise ValueError("result fingerprint mismatch")
        return self


class ExecutionInvocationRequest(_ExecutionContract):
    plan: ExecutionPlan
    approval_fingerprint: str

    _approval_fingerprint = field_validator("approval_fingerprint")(
        _checked_fingerprint
    )


class ExecutionVerificationRequest(_ExecutionContract):
    plan: ExecutionPlan
    result: ExecutionResultProjection
    timestamp: datetime

    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def execution_verification_fingerprint(
    *,
    execution_id: str,
    result_fingerprint: str,
    status: ExecutionVerificationStatus,
) -> str:
    return _fingerprint(
        {
            "execution_id": execution_id,
            "result_fingerprint": result_fingerprint,
            "status": status.value,
        }
    )


class ExecutionVerificationProjection(_ExecutionContract):
    execution_id: str
    result_fingerprint: str
    status: ExecutionVerificationStatus
    fingerprint: str

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _result_fingerprint = field_validator("result_fingerprint")(_checked_fingerprint)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> ExecutionVerificationProjection:
        if self.fingerprint != execution_verification_fingerprint(
            execution_id=self.execution_id,
            result_fingerprint=self.result_fingerprint,
            status=self.status,
        ):
            raise ValueError("verification fingerprint mismatch")
        return self


class ExecutionProgressEvent(_ExecutionContract):
    sequence: int
    execution_id: str
    workflow_id: str
    event: ExecutionProgressEventType
    state: ExecutionState
    timestamp: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
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


def execution_snapshot_fingerprint(
    *,
    plan: ExecutionPlan,
    state: ExecutionState,
    approval_fingerprint: str | None,
    result: ExecutionResultProjection | None,
    verification: ExecutionVerificationProjection | None,
    failure_code: ExecutionFailureCode | None,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "approval_fingerprint": approval_fingerprint,
            "failure_code": failure_code.value if failure_code is not None else None,
            "plan": plan.model_dump(mode="json"),
            "progress_sequence": progress_sequence,
            "result": result.model_dump(mode="json") if result is not None else None,
            "state": state.value,
            "verification": (
                verification.model_dump(mode="json")
                if verification is not None
                else None
            ),
        }
    )


class ExecutionSnapshot(_ExecutionContract):
    plan: ExecutionPlan
    state: ExecutionState
    approval_fingerprint: str | None = None
    result: ExecutionResultProjection | None = None
    verification: ExecutionVerificationProjection | None = None
    failure_code: ExecutionFailureCode | None = None
    progress_sequence: int
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("approval_fingerprint")
    @classmethod
    def _approval_fingerprint_format(cls, value: str | None) -> str | None:
        return None if value is None else _checked_fingerprint(value)

    @field_validator("progress_sequence")
    @classmethod
    def _progress_sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress_sequence is invalid")
        return value

    @model_validator(mode="after")
    def _state_and_fingerprint(self) -> ExecutionSnapshot:
        failure_states = {
            ExecutionState.FAILED,
            ExecutionState.TIMEOUT,
            ExecutionState.CANCELLED,
        }
        if (self.state in failure_states) != (self.failure_code is not None):
            raise ValueError("snapshot failure state is invalid")
        if self.state is ExecutionState.SUCCESS and (
            self.result is None
            or self.result.status is not ExecutionResultStatus.SUCCESS
            or self.verification is None
            or self.verification.status is not ExecutionVerificationStatus.VALID
        ):
            raise ValueError("successful snapshot is incomplete")
        if self.verification is not None:
            if self.result is None or (
                self.verification.execution_id != self.plan.execution_id
                or self.verification.result_fingerprint != self.result.fingerprint
            ):
                raise ValueError("verification binding mismatch")
        expected = execution_snapshot_fingerprint(
            plan=self.plan,
            state=self.state,
            approval_fingerprint=self.approval_fingerprint,
            result=self.result,
            verification=self.verification,
            failure_code=self.failure_code,
            progress_sequence=self.progress_sequence,
        )
        if self.fingerprint != expected:
            raise ValueError("snapshot fingerprint mismatch")
        return self
