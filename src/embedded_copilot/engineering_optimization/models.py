"""Immutable contracts for deterministic engineering optimization analysis."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")


class _OptimizationContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        revalidate_instances="always",
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _confidence(value: object) -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("confidence is invalid")
    return 0.0 if value == 0.0 else value


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def canonical_optimization_json(value: object) -> str:
    """Return canonical JSON used by v0.57 fingerprints."""

    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(kind: str, **values: object) -> str:
    encoded = canonical_optimization_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class OptimizationDomain(StrEnum):
    POWER = "POWER"
    PERFORMANCE = "PERFORMANCE"
    MEMORY = "MEMORY"
    COST = "COST"
    RELIABILITY = "RELIABILITY"


class OptimizationProposalState(StrEnum):
    PROPOSED = "PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class OptimizationReviewState(StrEnum):
    PENDING = "PENDING"


class OptimizationFindingCode(StrEnum):
    SOURCE_SIGNAL_REQUIRED = "SOURCE_SIGNAL_REQUIRED"
    VALIDATION_ISSUE_DETECTED = "VALIDATION_ISSUE_DETECTED"
    EXECUTION_ISSUE_DETECTED = "EXECUTION_ISSUE_DETECTED"
    FEEDBACK_CHANGE_REQUESTED = "FEEDBACK_CHANGE_REQUESTED"
    OPTIMIZATION_REVIEW_REQUIRED = "OPTIMIZATION_REVIEW_REQUIRED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"


class EngineeringOptimizationTarget(_OptimizationContract):
    optimization_id: str
    target_artifact_fingerprint: str
    domain: OptimizationDomain
    problem_reference: str
    current_state: str
    desired_state: str
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _target = field_validator("target_artifact_fingerprint")(_fingerprint_value)
    _problem = field_validator("problem_reference")(
        lambda value: _token(value, field="problem_reference")
    )
    _current = field_validator("current_state")(
        lambda value: _token(value, field="current_state")
    )
    _desired = field_validator("desired_state")(
        lambda value: _token(value, field="desired_state")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringOptimizationTarget:
        values = _values(self)
        if self.fingerprint != optimization_target_fingerprint(**values):
            raise ValueError("optimization target fingerprint mismatch")
        return self


def optimization_target_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringOptimizationTarget", **values)


class EngineeringTradeoffProjection(_OptimizationContract):
    option: str
    benefit: str
    risk: str
    cost: str
    confidence: float
    fingerprint: str

    _option = field_validator("option")(lambda value: _token(value, field="option"))
    _benefit = field_validator("benefit")(lambda value: _token(value, field="benefit"))
    _risk = field_validator("risk")(lambda value: _token(value, field="risk"))
    _cost = field_validator("cost")(lambda value: _token(value, field="cost"))
    _confidence_value = field_validator("confidence")(_confidence)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringTradeoffProjection:
        if self.fingerprint != engineering_tradeoff_fingerprint(**_values(self)):
            raise ValueError("tradeoff fingerprint mismatch")
        return self


def engineering_tradeoff_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringTradeoffProjection", **values)


class EngineeringOptimizationProposal(_OptimizationContract):
    optimization_id: str
    target_artifact_fingerprint: str
    domain: OptimizationDomain
    problem_reference: str
    current_state: str
    proposal: str
    expected_benefit: str
    tradeoffs: tuple[EngineeringTradeoffProjection, ...]
    risk: str
    confidence: float
    state: OptimizationProposalState
    review_required: Literal[True] = True
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _target = field_validator("target_artifact_fingerprint")(_fingerprint_value)
    _problem = field_validator("problem_reference")(
        lambda value: _token(value, field="problem_reference")
    )
    _current = field_validator("current_state")(
        lambda value: _token(value, field="current_state")
    )
    _proposal = field_validator("proposal")(
        lambda value: _token(value, field="proposal")
    )
    _benefit = field_validator("expected_benefit")(
        lambda value: _token(value, field="expected_benefit")
    )
    _risk = field_validator("risk")(lambda value: _token(value, field="risk"))
    _confidence_value = field_validator("confidence")(_confidence)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("tradeoffs", mode="before")
    @classmethod
    def validate_tradeoffs(cls, value: object) -> object:
        return _tuple(value, field="tradeoffs")

    @model_validator(mode="after")
    def validate_proposal(self) -> EngineeringOptimizationProposal:
        keys = tuple(item.option for item in self.tradeoffs)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("tradeoffs must be sorted and unique")
        if self.fingerprint != engineering_optimization_proposal_fingerprint(
            **_values(self)
        ):
            raise ValueError("optimization proposal fingerprint mismatch")
        return self


def engineering_optimization_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringOptimizationProposal", **values)


class OptimizationChangeProposal(_OptimizationContract):
    optimization_id: str
    optimization_proposal_fingerprint: str
    target_artifact_fingerprint: str
    domain: OptimizationDomain
    change_codes: tuple[str, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _proposal = field_validator("optimization_proposal_fingerprint")(_fingerprint_value)
    _target = field_validator("target_artifact_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("change_codes", mode="before")
    @classmethod
    def validate_change_codes(cls, value: object) -> object:
        value = _tuple(value, field="change_codes")
        keys = tuple(_token(item, field="change_code") for item in value)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("change codes must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> OptimizationChangeProposal:
        if self.fingerprint != optimization_change_proposal_fingerprint(
            **_values(self)
        ):
            raise ValueError("change proposal fingerprint mismatch")
        return self


def optimization_change_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("OptimizationChangeProposal", **values)


class OptimizationRevisionPlan(_OptimizationContract):
    optimization_id: str
    optimization_proposal_fingerprint: str
    base_artifact_fingerprint: str
    affected_domains: tuple[OptimizationDomain, ...]
    planned_changes: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _proposal = field_validator("optimization_proposal_fingerprint")(_fingerprint_value)
    _base = field_validator("base_artifact_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "affected_domains", "planned_changes", "validation_requirements", mode="before"
    )
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_plan(self) -> OptimizationRevisionPlan:
        domain_order = {value: index for index, value in enumerate(OptimizationDomain)}
        domain_keys = tuple(domain_order[item] for item in self.affected_domains)
        if (
            not domain_keys
            or domain_keys != tuple(sorted(domain_keys))
            or len(domain_keys) != len(set(domain_keys))
        ):
            raise ValueError("affected domains must be sorted and unique")
        for field_name in ("planned_changes", "validation_requirements"):
            items = getattr(self, field_name)
            keys = tuple(_token(item, field=field_name) for item in items)
            if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError(f"{field_name} must be sorted and unique")
        if self.fingerprint != optimization_revision_plan_fingerprint(**_values(self)):
            raise ValueError("revision plan fingerprint mismatch")
        return self


def optimization_revision_plan_fingerprint(**values: object) -> str:
    return _fingerprint("OptimizationRevisionPlan", **values)


class OptimizationValidationPlan(_OptimizationContract):
    optimization_id: str
    optimization_proposal_fingerprint: str
    target_artifact_fingerprint: str
    validation_requirements: tuple[str, ...]
    recommendation_only: Literal[True] = True
    review_required: Literal[True] = True
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _proposal = field_validator("optimization_proposal_fingerprint")(_fingerprint_value)
    _target = field_validator("target_artifact_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("validation_requirements", mode="before")
    @classmethod
    def validate_requirements(cls, value: object) -> object:
        value = _tuple(value, field="validation_requirements")
        keys = tuple(_token(item, field="validation_requirement") for item in value)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("validation requirements must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> OptimizationValidationPlan:
        if self.fingerprint != optimization_validation_plan_fingerprint(
            **_values(self)
        ):
            raise ValueError("validation plan fingerprint mismatch")
        return self


def optimization_validation_plan_fingerprint(**values: object) -> str:
    return _fingerprint("OptimizationValidationPlan", **values)


class EngineeringOptimizationReviewProjection(_OptimizationContract):
    request_id: str
    artifact_contract_fingerprint: str
    execution_report_fingerprint: str | None = None
    validation_report_fingerprint: str | None = None
    feedback_report_fingerprint: str | None = None
    proposal_count: int = Field(ge=0, le=64)
    change_proposal_count: int = Field(ge=0, le=64)
    revision_plan_count: int = Field(ge=0, le=64)
    validation_plan_count: int = Field(ge=0, le=64)
    finding_codes: tuple[OptimizationFindingCode, ...]
    state: Literal[OptimizationReviewState.PENDING] = OptimizationReviewState.PENDING
    review_required: Literal[True] = True
    fingerprint: str

    _request_id = field_validator("request_id")(
        lambda value: _identifier(value, field="request_id")
    )
    _artifact = field_validator("artifact_contract_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "execution_report_fingerprint",
        "validation_report_fingerprint",
        "feedback_report_fingerprint",
    )
    @classmethod
    def validate_optional_fingerprints(cls, value: object) -> str | None:
        return None if value is None else _fingerprint_value(value)

    @field_validator("finding_codes", mode="before")
    @classmethod
    def validate_findings(cls, value: object) -> object:
        return _tuple(value, field="finding_codes")

    @model_validator(mode="after")
    def validate_review(self) -> EngineeringOptimizationReviewProjection:
        order = {value: index for index, value in enumerate(OptimizationFindingCode)}
        keys = tuple(order[item] for item in self.finding_codes)
        if not keys or keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("optimization findings must be sorted and unique")
        if self.fingerprint != engineering_optimization_review_fingerprint(
            **_values(self)
        ):
            raise ValueError("optimization review fingerprint mismatch")
        return self


def engineering_optimization_review_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringOptimizationReviewProjection", **values)


class EngineeringOptimizationReport(_OptimizationContract):
    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    artifact_contract_fingerprint: str
    artifact_source_fingerprint: str
    proposals: tuple[EngineeringOptimizationProposal, ...]
    change_proposals: tuple[OptimizationChangeProposal, ...]
    revision_plans: tuple[OptimizationRevisionPlan, ...]
    validation_plans: tuple[OptimizationValidationPlan, ...]
    review: EngineeringOptimizationReviewProjection
    requested_at: datetime
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    _request_id = field_validator("request_id")(
        lambda value: _identifier(value, field="request_id")
    )
    _artifact = field_validator("artifact_contract_fingerprint")(_fingerprint_value)
    _source = field_validator("artifact_source_fingerprint")(_fingerprint_value)
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "proposals",
        "change_proposals",
        "revision_plans",
        "validation_plans",
        mode="before",
    )
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_report(self) -> EngineeringOptimizationReport:
        collections = (
            self.proposals,
            self.change_proposals,
            self.revision_plans,
            self.validation_plans,
        )
        for collection in collections:
            keys = tuple(item.optimization_id for item in collection)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError(
                    "optimization report collections must be sorted and unique"
                )
        expected_count = len(self.proposals)
        if any(len(collection) != expected_count for collection in collections[1:]):
            raise ValueError("optimization report projection counts mismatch")
        if (
            self.review.request_id != self.request_id
            or self.review.artifact_contract_fingerprint
            != self.artifact_contract_fingerprint
            or self.review.proposal_count != expected_count
            or self.review.change_proposal_count != len(self.change_proposals)
            or self.review.revision_plan_count != len(self.revision_plans)
            or self.review.validation_plan_count != len(self.validation_plans)
        ):
            raise ValueError("optimization report binding mismatch")
        if self.fingerprint != engineering_optimization_report_fingerprint(
            **_values(self, exclude=("schema_version",))
        ):
            raise ValueError("optimization report fingerprint mismatch")
        return self


def engineering_optimization_report_fingerprint(**values: object) -> str:
    values.pop("schema_version", None)
    return _fingerprint("EngineeringOptimizationReport", **values)


def _values(model: BaseModel, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    excluded = {"fingerprint", *exclude}
    return {
        name: getattr(model, name)
        for name in type(model).model_fields
        if name not in excluded
    }


__all__ = (
    "EngineeringOptimizationProposal",
    "EngineeringOptimizationReport",
    "EngineeringOptimizationReviewProjection",
    "EngineeringOptimizationTarget",
    "EngineeringTradeoffProjection",
    "OptimizationChangeProposal",
    "OptimizationDomain",
    "OptimizationFindingCode",
    "OptimizationProposalState",
    "OptimizationRevisionPlan",
    "OptimizationReviewState",
    "OptimizationValidationPlan",
    "canonical_optimization_json",
    "engineering_optimization_proposal_fingerprint",
    "engineering_optimization_report_fingerprint",
    "engineering_optimization_review_fingerprint",
    "engineering_tradeoff_fingerprint",
    "optimization_change_proposal_fingerprint",
    "optimization_revision_plan_fingerprint",
    "optimization_target_fingerprint",
    "optimization_validation_plan_fingerprint",
)
