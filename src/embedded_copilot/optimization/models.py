"""Immutable public contracts for proposal-only optimization."""

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
_METRIC_NAME = r"^[a-z][a-z0-9_]{0,63}$"
_OBJECTIVE = r"^[A-Z][A-Z0-9_]{2,63}$"
_FINGERPRINT = r"^sha256:[a-f0-9]{64}$"
_SENSITIVE = (
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])"
)
_ABSOLUTE_PATH = r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)"


class _OptimizationContract(BaseModel):
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


def _metric_name(value: object) -> str:
    if type(value) is not str or re.fullmatch(_METRIC_NAME, value) is None:
        raise ValueError("metric name is invalid")
    return value


def _safe_summary(value: object) -> str:
    if type(value) is not str:
        raise ValueError("summary is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > 1024
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or re.search(_SENSITIVE, candidate, re.IGNORECASE) is not None
        or re.search(_ABSOLUTE_PATH, candidate) is not None
    ):
        raise ValueError("summary is unsafe")
    return candidate


def _utc(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timestamp must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _finite(value: object, *, field: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
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


class OptimizationTarget(StrEnum):
    POWER = "POWER"
    PERFORMANCE = "PERFORMANCE"
    BALANCED = "BALANCED"


class OptimizationAlgorithm(StrEnum):
    PID = "PID"
    POWER_MODEL = "POWER_MODEL"
    PERFORMANCE_MODEL = "PERFORMANCE_MODEL"


class OptimizationMetricUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    MILLISECONDS = "milliseconds"
    CELSIUS = "celsius"
    VOLTS = "volts"
    AMPERES = "amperes"
    WATTS = "watts"
    HERTZ = "hertz"
    RPM = "rpm"
    RATIO = "ratio"


class OptimizationRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class OptimizationEvaluationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class OptimizationApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OptimizationState(StrEnum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class OptimizationFailureCode(StrEnum):
    REGISTRY_UNAVAILABLE = "registry_unavailable"
    OPTIMIZER_REJECTED = "optimizer_rejected"
    OPTIMIZER_TIMEOUT = "optimizer_timeout"
    EVALUATOR_UNAVAILABLE = "evaluator_unavailable"
    EVALUATION_INVALID = "evaluation_invalid"
    EVALUATION_TIMEOUT = "evaluation_timeout"
    APPROVAL_REJECTED = "approval_rejected"


class OptimizationProgressEventType(StrEnum):
    OPTIMIZATION_CREATED = "OPTIMIZATION_CREATED"
    OPTIMIZATION_PLANNED = "OPTIMIZATION_PLANNED"
    EVALUATION_RUNNING = "EVALUATION_RUNNING"
    OPTIMIZATION_EVALUATED = "OPTIMIZATION_EVALUATED"
    OPTIMIZATION_APPROVED = "OPTIMIZATION_APPROVED"
    OPTIMIZATION_SUCCEEDED = "OPTIMIZATION_SUCCEEDED"
    OPTIMIZATION_FAILED = "OPTIMIZATION_FAILED"
    OPTIMIZATION_TIMED_OUT = "OPTIMIZATION_TIMED_OUT"
    OPTIMIZATION_CANCELLED = "OPTIMIZATION_CANCELLED"


class OptimizationMetric(_OptimizationContract):
    name: str
    value: int | float
    unit: OptimizationMetricUnit

    _name = field_validator("name")(_metric_name)
    _value = field_validator("value")(
        lambda value: _finite(value, field="metric value")
    )


class OptimizationConstraint(_OptimizationContract):
    parameter: str
    current: int | float
    minimum: int | float
    maximum: int | float
    unit: OptimizationMetricUnit

    _parameter = field_validator("parameter")(_metric_name)
    _current = field_validator("current")(
        lambda value: _finite(value, field="constraint current")
    )
    _minimum = field_validator("minimum")(
        lambda value: _finite(value, field="constraint minimum")
    )
    _maximum = field_validator("maximum")(
        lambda value: _finite(value, field="constraint maximum")
    )

    @model_validator(mode="after")
    def _bounds(self) -> OptimizationConstraint:
        if not self.minimum <= self.current <= self.maximum:
            raise ValueError("constraint bounds are invalid")
        return self


class OptimizationParameterRange(_OptimizationContract):
    parameter: str
    minimum: int | float
    maximum: int | float
    unit: OptimizationMetricUnit

    _parameter = field_validator("parameter")(_metric_name)
    _minimum = field_validator("minimum")(
        lambda value: _finite(value, field="parameter minimum")
    )
    _maximum = field_validator("maximum")(
        lambda value: _finite(value, field="parameter maximum")
    )

    @model_validator(mode="after")
    def _bounds(self) -> OptimizationParameterRange:
        if self.minimum > self.maximum:
            raise ValueError("parameter range is invalid")
        return self


class OptimizationParameterChange(_OptimizationContract):
    parameter: str
    before: int | float
    after: int | float
    unit: OptimizationMetricUnit

    _parameter = field_validator("parameter")(_metric_name)
    _before = field_validator("before")(
        lambda value: _finite(value, field="parameter before")
    )
    _after = field_validator("after")(
        lambda value: _finite(value, field="parameter after")
    )


def optimization_context_fingerprint(
    *, context_id: str, summary: str, reference_ids: tuple[str, ...]
) -> str:
    return _fingerprint(
        {
            "context_id": context_id,
            "reference_ids": list(reference_ids),
            "summary": summary,
        }
    )


class OptimizationContextProjection(_OptimizationContract):
    context_id: str
    summary: str
    reference_ids: tuple[str, ...]
    fingerprint: str

    _context_id = field_validator("context_id")(
        lambda value: _identifier(value, field="context_id")
    )
    _summary = field_validator("summary")(_safe_summary)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def _references_tuple(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @field_validator("reference_ids")
    @classmethod
    def _references(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_identifier(item, field="reference_id") for item in value)
        if (
            not checked
            or checked != tuple(sorted(checked))
            or len(checked) != len(set(checked))
        ):
            raise ValueError("reference_ids must be sorted and unique")
        return checked

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> OptimizationContextProjection:
        if self.fingerprint != optimization_context_fingerprint(
            context_id=self.context_id,
            summary=self.summary,
            reference_ids=self.reference_ids,
        ):
            raise ValueError("context fingerprint mismatch")
        return self


_TARGET_MATRIX = {
    OptimizationTarget.POWER: OptimizationAlgorithm.POWER_MODEL,
    OptimizationTarget.PERFORMANCE: OptimizationAlgorithm.PERFORMANCE_MODEL,
    OptimizationTarget.BALANCED: OptimizationAlgorithm.PID,
}


def optimization_request_fingerprint(request: OptimizationRequest) -> str:
    return _fingerprint(request.model_dump(mode="json"))


class OptimizationRequest(_OptimizationContract):
    optimization_id: str
    hardware_context: OptimizationContextProjection
    target: OptimizationTarget
    algorithm: OptimizationAlgorithm
    baseline_metrics: tuple[OptimizationMetric, ...]
    constraints: tuple[OptimizationConstraint, ...]
    timestamp: datetime

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _timestamp = field_validator("timestamp")(_utc)

    @field_validator("baseline_metrics", "constraints", mode="before")
    @classmethod
    def _collections_tuple(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def _collections_and_matrix(self) -> OptimizationRequest:
        metric_names = tuple(item.name for item in self.baseline_metrics)
        constraint_names = tuple(item.parameter for item in self.constraints)
        if (
            not metric_names
            or len(metric_names) > 64
            or metric_names != tuple(sorted(metric_names))
            or len(metric_names) != len(set(metric_names))
        ):
            raise ValueError("baseline_metrics must be sorted and unique")
        if (
            not constraint_names
            or len(constraint_names) > 32
            or constraint_names != tuple(sorted(constraint_names))
            or len(constraint_names) != len(set(constraint_names))
        ):
            raise ValueError("constraints must be sorted and unique")
        if _TARGET_MATRIX[self.target] is not self.algorithm:
            raise ValueError("target and algorithm are incompatible")
        return self


class OptimizationResolutionRequest(_OptimizationContract):
    optimization_id: str
    target: OptimizationTarget
    algorithm: OptimizationAlgorithm
    request_fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _request_fingerprint = field_validator("request_fingerprint")(_checked_fingerprint)


def optimization_algorithm_metadata_fingerprint(
    *,
    algorithm: OptimizationAlgorithm,
    target: OptimizationTarget,
    parameter_space: tuple[OptimizationParameterRange, ...],
    objective: str,
) -> str:
    return _fingerprint(
        {
            "algorithm": algorithm.value,
            "objective": objective,
            "parameter_space": [
                item.model_dump(mode="json") for item in parameter_space
            ],
            "target": target.value,
        }
    )


class OptimizationAlgorithmMetadata(_OptimizationContract):
    algorithm: OptimizationAlgorithm
    target: OptimizationTarget
    parameter_space: tuple[OptimizationParameterRange, ...]
    objective: str
    fingerprint: str

    _objective = field_validator("objective")(
        lambda value: (
            value
            if type(value) is str and re.fullmatch(_OBJECTIVE, value)
            else (_ for _ in ()).throw(ValueError("objective is invalid"))
        )
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("parameter_space", mode="before")
    @classmethod
    def _parameter_tuple(cls, value: object) -> object:
        return _tuple(value, field="parameter_space")

    @model_validator(mode="after")
    def _parameters_and_fingerprint(self) -> OptimizationAlgorithmMetadata:
        names = tuple(item.parameter for item in self.parameter_space)
        if not names or names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("parameter_space must be sorted and unique")
        if self.fingerprint != optimization_algorithm_metadata_fingerprint(
            algorithm=self.algorithm,
            target=self.target,
            parameter_space=self.parameter_space,
            objective=self.objective,
        ):
            raise ValueError("algorithm metadata fingerprint mismatch")
        return self


def optimization_plan_fingerprint(
    *,
    request: OptimizationRequest,
    request_fingerprint: str,
    algorithm_metadata: OptimizationAlgorithmMetadata,
    parameter_space: tuple[OptimizationParameterRange, ...],
    objective: str,
) -> str:
    return _fingerprint(
        {
            "algorithm_metadata": algorithm_metadata.model_dump(mode="json"),
            "objective": objective,
            "parameter_space": [
                item.model_dump(mode="json") for item in parameter_space
            ],
            "request": request.model_dump(mode="json"),
            "request_fingerprint": request_fingerprint,
        }
    )


class OptimizationPlan(_OptimizationContract):
    request: OptimizationRequest
    request_fingerprint: str
    algorithm_metadata: OptimizationAlgorithmMetadata
    parameter_space: tuple[OptimizationParameterRange, ...]
    objective: str
    fingerprint: str

    _request_fingerprint = field_validator("request_fingerprint")(_checked_fingerprint)
    _objective = field_validator("objective")(
        lambda value: (
            value
            if type(value) is str and re.fullmatch(_OBJECTIVE, value)
            else (_ for _ in ()).throw(ValueError("objective is invalid"))
        )
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("parameter_space", mode="before")
    @classmethod
    def _parameter_tuple(cls, value: object) -> object:
        return _tuple(value, field="parameter_space")

    @model_validator(mode="after")
    def _bindings_and_fingerprint(self) -> OptimizationPlan:
        names = tuple(item.parameter for item in self.parameter_space)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("plan parameter space is invalid")
        if (
            self.request_fingerprint != optimization_request_fingerprint(self.request)
            or self.algorithm_metadata.algorithm is not self.request.algorithm
            or self.algorithm_metadata.target is not self.request.target
            or self.objective != self.algorithm_metadata.objective
        ):
            raise ValueError("plan binding mismatch")
        if self.fingerprint != optimization_plan_fingerprint(
            request=self.request,
            request_fingerprint=self.request_fingerprint,
            algorithm_metadata=self.algorithm_metadata,
            parameter_space=self.parameter_space,
            objective=self.objective,
        ):
            raise ValueError("plan fingerprint mismatch")
        return self


class OptimizationInvocationRequest(_OptimizationContract):
    plan: OptimizationPlan
    timestamp: datetime

    _timestamp = field_validator("timestamp")(_utc)


def optimization_proposal_fingerprint(
    *,
    optimization_id: str,
    plan_fingerprint: str,
    candidate_semantics: str,
    parameter_changes: tuple[OptimizationParameterChange, ...],
    expected_gain: float,
    risk_level: OptimizationRiskLevel,
    metrics_projection: tuple[OptimizationMetric, ...],
) -> str:
    return _fingerprint(
        {
            "candidate_semantics": candidate_semantics,
            "expected_gain": expected_gain,
            "metrics_projection": [
                item.model_dump(mode="json") for item in metrics_projection
            ],
            "optimization_id": optimization_id,
            "parameter_changes": [
                item.model_dump(mode="json") for item in parameter_changes
            ],
            "plan_fingerprint": plan_fingerprint,
            "risk_level": risk_level.value,
        }
    )


class OptimizationProposal(_OptimizationContract):
    optimization_id: str
    plan_fingerprint: str
    candidate_semantics: Literal["unverified"] = "unverified"
    parameter_changes: tuple[OptimizationParameterChange, ...]
    expected_gain: float
    risk_level: OptimizationRiskLevel
    metrics_projection: tuple[OptimizationMetric, ...]
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_checked_fingerprint)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("expected_gain")
    @classmethod
    def _gain(cls, value: float) -> float:
        checked = _finite(value, field="expected_gain")
        if not 0.0 <= checked <= 100.0:
            raise ValueError("expected_gain is invalid")
        return float(checked)

    @field_validator("parameter_changes", "metrics_projection", mode="before")
    @classmethod
    def _collections_tuple(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def _collections_and_fingerprint(self) -> OptimizationProposal:
        changes = tuple(item.parameter for item in self.parameter_changes)
        metrics = tuple(item.name for item in self.metrics_projection)
        if (
            not changes
            or changes != tuple(sorted(changes))
            or len(changes) != len(set(changes))
            or not metrics
            or metrics != tuple(sorted(metrics))
            or len(metrics) != len(set(metrics))
        ):
            raise ValueError("proposal collections are invalid")
        if self.fingerprint != optimization_proposal_fingerprint(
            optimization_id=self.optimization_id,
            plan_fingerprint=self.plan_fingerprint,
            candidate_semantics=self.candidate_semantics,
            parameter_changes=self.parameter_changes,
            expected_gain=self.expected_gain,
            risk_level=self.risk_level,
            metrics_projection=self.metrics_projection,
        ):
            raise ValueError("proposal fingerprint mismatch")
        return self


class OptimizationEvaluationRequest(_OptimizationContract):
    plan: OptimizationPlan
    proposal: OptimizationProposal
    timestamp: datetime

    _timestamp = field_validator("timestamp")(_utc)

    @model_validator(mode="after")
    def _binding(self) -> OptimizationEvaluationRequest:
        if (
            self.proposal.optimization_id != self.plan.request.optimization_id
            or self.proposal.plan_fingerprint != self.plan.fingerprint
        ):
            raise ValueError("evaluation request binding mismatch")
        return self


class OptimizationImprovement(_OptimizationContract):
    metric_name: str
    unit: OptimizationMetricUnit
    before: int | float
    after: int | float
    delta: float
    percent_change: float | None

    _metric_name = field_validator("metric_name")(_metric_name)
    _before = field_validator("before")(
        lambda value: _finite(value, field="improvement before")
    )
    _after = field_validator("after")(
        lambda value: _finite(value, field="improvement after")
    )
    _delta = field_validator("delta")(
        lambda value: float(_finite(value, field="improvement delta"))
    )

    @field_validator("percent_change")
    @classmethod
    def _percent(cls, value: float | None) -> float | None:
        return (
            None
            if value is None
            else float(_finite(value, field="improvement percent"))
        )

    @model_validator(mode="after")
    def _calculation(self) -> OptimizationImprovement:
        expected_delta = float(self.after - self.before)
        expected_percent = (
            None
            if self.before == 0
            else float(expected_delta / abs(self.before) * 100.0)
        )
        if not math.isclose(self.delta, expected_delta, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("improvement delta mismatch")
        if (self.percent_change is None) != (expected_percent is None):
            raise ValueError("improvement percent mismatch")
        if expected_percent is not None and not math.isclose(
            self.percent_change, expected_percent, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError("improvement percent mismatch")
        return self


def optimization_evaluation_fingerprint(
    *,
    optimization_id: str,
    proposal_fingerprint: str,
    before_metrics: tuple[OptimizationMetric, ...],
    after_metrics: tuple[OptimizationMetric, ...],
    improvement: tuple[OptimizationImprovement, ...],
    validation_status: OptimizationEvaluationStatus,
) -> str:
    return _fingerprint(
        {
            "after_metrics": [item.model_dump(mode="json") for item in after_metrics],
            "before_metrics": [item.model_dump(mode="json") for item in before_metrics],
            "improvement": [item.model_dump(mode="json") for item in improvement],
            "optimization_id": optimization_id,
            "proposal_fingerprint": proposal_fingerprint,
            "validation_status": validation_status.value,
        }
    )


class OptimizationEvaluationProjection(_OptimizationContract):
    optimization_id: str
    proposal_fingerprint: str
    before_metrics: tuple[OptimizationMetric, ...]
    after_metrics: tuple[OptimizationMetric, ...]
    improvement: tuple[OptimizationImprovement, ...]
    validation_status: OptimizationEvaluationStatus
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("before_metrics", "after_metrics", "improvement", mode="before")
    @classmethod
    def _collections_tuple(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def _collections_and_fingerprint(self) -> OptimizationEvaluationProjection:
        before = tuple((item.name, item.unit) for item in self.before_metrics)
        after = tuple((item.name, item.unit) for item in self.after_metrics)
        improvements = tuple((item.metric_name, item.unit) for item in self.improvement)
        if (
            not before
            or before != tuple(sorted(before))
            or before != after
            or before != improvements
            or len(before) != len(set(before))
        ):
            raise ValueError("evaluation metrics are invalid")
        if self.fingerprint != optimization_evaluation_fingerprint(
            optimization_id=self.optimization_id,
            proposal_fingerprint=self.proposal_fingerprint,
            before_metrics=self.before_metrics,
            after_metrics=self.after_metrics,
            improvement=self.improvement,
            validation_status=self.validation_status,
        ):
            raise ValueError("evaluation fingerprint mismatch")
        return self


class OptimizationProgressEvent(_OptimizationContract):
    sequence: int
    optimization_id: str
    state: OptimizationState
    event: OptimizationProgressEventType
    timestamp: datetime

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _timestamp = field_validator("timestamp")(_utc)

    @field_validator("sequence")
    @classmethod
    def _sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("sequence is invalid")
        return value


def optimization_snapshot_fingerprint(
    *,
    request: OptimizationRequest,
    plan: OptimizationPlan | None,
    proposal: OptimizationProposal | None,
    evaluation: OptimizationEvaluationProjection | None,
    approval: object | None,
    state: OptimizationState,
    failure_code: OptimizationFailureCode | None,
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "approval": (
                approval.model_dump(mode="json") if approval is not None else None
            ),
            "evaluation": (
                evaluation.model_dump(mode="json") if evaluation is not None else None
            ),
            "failure_code": failure_code.value if failure_code else None,
            "plan": plan.model_dump(mode="json") if plan is not None else None,
            "progress_sequence": progress_sequence,
            "proposal": (
                proposal.model_dump(mode="json") if proposal is not None else None
            ),
            "request": request.model_dump(mode="json"),
            "state": state.value,
        }
    )


class OptimizationSnapshot(_OptimizationContract):
    request: OptimizationRequest
    plan: OptimizationPlan | None = None
    proposal: OptimizationProposal | None = None
    evaluation: OptimizationEvaluationProjection | None = None
    approval: object | None = None
    state: OptimizationState
    failure_code: OptimizationFailureCode | None = None
    progress_sequence: int
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("approval", mode="before")
    @classmethod
    def _typed_approval(cls, value: object) -> object:
        if value is None:
            return None
        from embedded_copilot.optimization.approval.context import (
            OptimizationApprovalContext,
        )

        if type(value) is not OptimizationApprovalContext:
            raise ValueError("approval must be a typed context")
        return OptimizationApprovalContext.model_validate(value.model_copy(deep=True))

    @field_validator("progress_sequence")
    @classmethod
    def _sequence(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress_sequence is invalid")
        return value

    @model_validator(mode="after")
    def _state_and_fingerprint(self) -> OptimizationSnapshot:
        terminal_failure = self.state in {
            OptimizationState.FAILED,
            OptimizationState.TIMEOUT,
            OptimizationState.CANCELLED,
        }
        if terminal_failure != (self.failure_code is not None):
            raise ValueError("snapshot failure state is invalid")
        if self.state in {
            OptimizationState.PLANNED,
            OptimizationState.RUNNING,
            OptimizationState.EVALUATED,
            OptimizationState.APPROVED,
            OptimizationState.SUCCESS,
            OptimizationState.CANCELLED,
        } and (self.plan is None or self.proposal is None):
            raise ValueError("planned snapshot is incomplete")
        if (
            self.state
            in {
                OptimizationState.EVALUATED,
                OptimizationState.APPROVED,
                OptimizationState.SUCCESS,
                OptimizationState.CANCELLED,
            }
            and self.evaluation is None
        ):
            raise ValueError("evaluated snapshot is incomplete")
        if (
            self.state
            in {
                OptimizationState.APPROVED,
                OptimizationState.SUCCESS,
                OptimizationState.CANCELLED,
            }
            and self.approval is None
        ):
            raise ValueError("approved snapshot is incomplete")
        if self.plan is not None and self.plan.request != self.request:
            raise ValueError("snapshot request binding mismatch")
        if self.proposal is not None and (
            self.plan is None
            or self.proposal.optimization_id != self.request.optimization_id
            or self.proposal.plan_fingerprint != self.plan.fingerprint
        ):
            raise ValueError("snapshot proposal binding mismatch")
        if self.evaluation is not None and (
            self.proposal is None
            or self.evaluation.proposal_fingerprint != self.proposal.fingerprint
        ):
            raise ValueError("snapshot evaluation binding mismatch")
        if self.fingerprint != optimization_snapshot_fingerprint(
            request=self.request,
            plan=self.plan,
            proposal=self.proposal,
            evaluation=self.evaluation,
            approval=self.approval,
            state=self.state,
            failure_code=self.failure_code,
            progress_sequence=self.progress_sequence,
        ):
            raise ValueError("snapshot fingerprint mismatch")
        return self
