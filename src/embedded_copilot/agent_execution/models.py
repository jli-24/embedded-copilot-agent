"""Immutable contracts for the Agent Execution Runtime."""

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
_AGENT_TYPE = r"^[A-Z][A-Z0-9_]{2,63}$"
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


def _agent_type(value: object) -> str:
    if type(value) is not str or re.fullmatch(_AGENT_TYPE, value) is None:
        raise ValueError("agent_type is invalid")
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


class ExecutionContextSourceType(StrEnum):
    WORKFLOW = "WORKFLOW"
    KNOWLEDGE = "KNOWLEDGE"
    MEMORY = "MEMORY"
    PROJECT = "PROJECT"
    ARTIFACT = "ARTIFACT"


class AgentExecutionResultStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ExecutionVerificationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class ExecutionApprovalDecision(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"


class AgentExecutionState(StrEnum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    WAIT_HUMAN = "WAIT_HUMAN"
    CANCELLED = "CANCELLED"


class ExecutionFailureCode(StrEnum):
    AGENT_UNAVAILABLE = "agent_unavailable"
    AGENT_TIMEOUT = "agent_timeout"
    AGENT_RESULT_REJECTED = "agent_result_rejected"
    AGENT_FAILED = "agent_failed"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    VERIFICATION_INVALID = "verification_invalid"
    APPROVAL_DENIED = "approval_denied"


class ExecutionMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"


class ExecutionContextReference(_ExecutionContract):
    source_type: ExecutionContextSourceType
    reference_id: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )


class AgentExecutionInputContext(_ExecutionContract):
    context_id: str
    summary: str
    references: tuple[ExecutionContextReference, ...]

    _context_id = field_validator("context_id")(
        lambda value: _identifier(value, field="context_id")
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary")
    )

    @field_validator("references", mode="before")
    @classmethod
    def _references_tuple(cls, value: object) -> object:
        return _tuple(value, field="references")

    @field_validator("references")
    @classmethod
    def _references_unique(
        cls, value: tuple[ExecutionContextReference, ...]
    ) -> tuple[ExecutionContextReference, ...]:
        keys = tuple((item.source_type.value, item.reference_id) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("references must be sorted and unique")
        return value


class AgentExecutionRequest(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    input_context: AgentExecutionInputContext
    constraints: tuple[str, ...]
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
    _agent_type = field_validator("agent_type")(_agent_type)
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("constraints", mode="before")
    @classmethod
    def _constraints_tuple(cls, value: object) -> object:
        return _tuple(value, field="constraints")

    @field_validator("constraints")
    @classmethod
    def _constraints_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(
            _safe_text(item, field="constraint", maximum=512) for item in value
        )
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("constraints must be sorted and unique")
        return checked


class AgentResolutionRequest(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    attempt: int

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _agent_type = field_validator("agent_type")(_agent_type)

    @field_validator("attempt")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if type(value) is not int or value not in (1, 2):
            raise ValueError("attempt is invalid")
        return value


def agent_binding_fingerprint(
    *, binding_id: str, agent_type: str, capabilities: tuple[str, ...]
) -> str:
    return _fingerprint(
        {
            "agent_type": agent_type,
            "binding_id": binding_id,
            "capabilities": list(capabilities),
        }
    )


class AgentBindingMetadata(_ExecutionContract):
    binding_id: str
    agent_type: str
    capabilities: tuple[str, ...]
    fingerprint: str

    _binding_id = field_validator("binding_id")(
        lambda value: _identifier(value, field="binding_id")
    )
    _agent_type = field_validator("agent_type")(_agent_type)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("capabilities", mode="before")
    @classmethod
    def _capabilities_tuple(cls, value: object) -> object:
        return _tuple(value, field="capabilities")

    @field_validator("capabilities")
    @classmethod
    def _capabilities_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_agent_type(item) for item in value)
        if (
            not checked
            or checked != tuple(sorted(checked))
            or len(checked) != len(set(checked))
        ):
            raise ValueError("capabilities must be sorted and unique")
        return checked

    @model_validator(mode="after")
    def _fingerprint_valid(self) -> AgentBindingMetadata:
        expected = agent_binding_fingerprint(
            binding_id=self.binding_id,
            agent_type=self.agent_type,
            capabilities=self.capabilities,
        )
        if self.fingerprint != expected:
            raise ValueError("binding fingerprint mismatch")
        return self


class AgentInvocationRequest(_ExecutionContract):
    request: AgentExecutionRequest
    attempt: int

    @field_validator("attempt")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if type(value) is not int or value not in (1, 2):
            raise ValueError("attempt is invalid")
        return value


class ExecutionArtifactReference(_ExecutionContract):
    reference_id: str
    artifact_type: str
    status: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _artifact_type = field_validator("artifact_type")(_agent_type)
    _status = field_validator("status")(_agent_type)


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


def agent_execution_result_fingerprint(
    *,
    execution_id: str,
    workflow_id: str,
    task_id: str,
    agent_type: str,
    status: AgentExecutionResultStatus,
    summary: str,
    artifacts: tuple[ExecutionArtifactReference, ...],
    metrics: tuple[ExecutionMetric, ...],
) -> str:
    return _fingerprint(
        {
            "agent_type": agent_type,
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
            "execution_id": execution_id,
            "metrics": [item.model_dump(mode="json") for item in metrics],
            "status": status.value,
            "summary": summary,
            "task_id": task_id,
            "workflow_id": workflow_id,
        }
    )


class AgentExecutionResult(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    status: AgentExecutionResultStatus
    summary: str
    artifacts: tuple[ExecutionArtifactReference, ...]
    metrics: tuple[ExecutionMetric, ...]
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
    _agent_type = field_validator("agent_type")(_agent_type)
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("artifacts", "metrics", mode="before")
    @classmethod
    def _tuple_fields(cls, value: object) -> object:
        return _tuple(value, field="collection")

    @model_validator(mode="after")
    def _collections_valid(self) -> AgentExecutionResult:
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
        return self

    @model_validator(mode="after")
    def _fingerprint_valid(self) -> AgentExecutionResult:
        expected = agent_execution_result_fingerprint(
            execution_id=self.execution_id,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            agent_type=self.agent_type,
            status=self.status,
            summary=self.summary,
            artifacts=self.artifacts,
            metrics=self.metrics,
        )
        if self.fingerprint != expected:
            raise ValueError("result fingerprint mismatch")
        return self


class ExecutionResultProjection(_ExecutionContract):
    status: AgentExecutionResultStatus
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
    def _tuple_fields(cls, value: object) -> object:
        return _tuple(value, field="collection")


class ExecutionVerificationRequest(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    attempt: int
    result: AgentExecutionResult
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
    _agent_type = field_validator("agent_type")(_agent_type)
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("attempt")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if type(value) is not int or value not in (1, 2):
            raise ValueError("attempt is invalid")
        return value


def execution_verification_result_fingerprint(
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


class ExecutionVerificationResult(_ExecutionContract):
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
    def _fingerprint_valid(self) -> ExecutionVerificationResult:
        expected = execution_verification_result_fingerprint(
            execution_id=self.execution_id,
            result_fingerprint=self.result_fingerprint,
            status=self.status,
        )
        if self.fingerprint != expected:
            raise ValueError("verification fingerprint mismatch")
        return self


class ExecutionProgressEvent(_ExecutionContract):
    sequence: int
    execution_id: str
    workflow_id: str
    state: AgentExecutionState
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


class ExecutionApprovalContext(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    attempt: int
    snapshot_fingerprint: str
    decision: ExecutionApprovalDecision
    reviewer: str
    reviewed_at: datetime

    _execution_id = field_validator("execution_id")(
        lambda value: _identifier(value, field="execution_id")
    )
    _workflow_id = field_validator("workflow_id")(
        lambda value: _identifier(value, field="workflow_id")
    )
    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _agent_type = field_validator("agent_type")(_agent_type)
    _snapshot_fingerprint = field_validator("snapshot_fingerprint")(
        _checked_fingerprint
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _reviewed_at = field_validator("reviewed_at")(
        lambda value: _utc(value, field="reviewed_at")
    )

    @field_validator("attempt")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if type(value) is not int or value not in (1, 2):
            raise ValueError("attempt is invalid")
        return value


def agent_execution_snapshot_fingerprint(
    *,
    execution_id: str,
    workflow_id: str,
    task_id: str,
    agent_type: str,
    request: AgentExecutionRequest,
    state: AgentExecutionState,
    attempt: int,
    result_projection: ExecutionResultProjection | None,
    failure_code: ExecutionFailureCode | None,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "agent_type": agent_type,
            "attempt": attempt,
            "execution_id": execution_id,
            "failure_code": failure_code.value if failure_code else None,
            "progress_sequence": progress_sequence,
            "request": request.model_dump(mode="json"),
            "result_projection": (
                result_projection.model_dump(mode="json")
                if result_projection is not None
                else None
            ),
            "state": state.value,
            "task_id": task_id,
            "workflow_id": workflow_id,
        }
    )


class AgentExecutionSnapshot(_ExecutionContract):
    execution_id: str
    workflow_id: str
    task_id: str
    agent_type: str
    request: AgentExecutionRequest
    state: AgentExecutionState
    attempt: int
    result_projection: ExecutionResultProjection | None = None
    failure_code: ExecutionFailureCode | None = None
    progress_sequence: int
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
    _agent_type = field_validator("agent_type")(_agent_type)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("attempt")
    @classmethod
    def _attempt(cls, value: int) -> int:
        if type(value) is not int or value not in (1, 2):
            raise ValueError("attempt is invalid")
        return value

    @field_validator("progress_sequence")
    @classmethod
    def _progress_sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress sequence is invalid")
        return value

    @model_validator(mode="after")
    def _bindings_valid(self) -> AgentExecutionSnapshot:
        if (
            self.execution_id != self.request.execution_id
            or self.workflow_id != self.request.workflow_id
            or self.task_id != self.request.task_id
            or self.agent_type != self.request.agent_type
        ):
            raise ValueError("snapshot binding mismatch")
        failure_states = {
            AgentExecutionState.FAILED,
            AgentExecutionState.TIMEOUT,
            AgentExecutionState.CANCELLED,
        }
        if (self.state in failure_states) != (self.failure_code is not None):
            raise ValueError("snapshot failure state is invalid")
        expected = agent_execution_snapshot_fingerprint(
            execution_id=self.execution_id,
            workflow_id=self.workflow_id,
            task_id=self.task_id,
            agent_type=self.agent_type,
            request=self.request,
            state=self.state,
            attempt=self.attempt,
            result_projection=self.result_projection,
            failure_code=self.failure_code,
            progress_sequence=self.progress_sequence,
        )
        if self.fingerprint != expected:
            raise ValueError("snapshot fingerprint mismatch")
        return self
