from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


AgentLatencyStatus = Literal["unavailable"]
EvaluationFailureCode = Literal[
    "supervisor_execution_failed",
    "engineering_report_missing",
    "engineering_report_invalid",
    "evaluation_failed",
]
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


class _EvaluationModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    @field_validator("case_id", "version", "dataset", mode="before", check_fields=False)
    @classmethod
    def validate_identifier(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if not _SAFE_IDENTIFIER.fullmatch(candidate):
            raise ValueError("evaluation identifier is invalid")
        return candidate


class EvaluationCaseResult(_EvaluationModel):
    case_id: str
    success: bool
    routing_accuracy: float = Field(ge=0, le=1, allow_inf_nan=False)
    agent_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    report_completeness: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_traceability: float = Field(ge=0, le=1, allow_inf_nan=False)
    execution_latency_ms: float = Field(ge=0, allow_inf_nan=False)
    agent_latency_status: AgentLatencyStatus = "unavailable"
    failure_code: EvaluationFailureCode | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "EvaluationCaseResult":
        quality = (
            self.routing_accuracy,
            self.agent_success_rate,
            self.report_completeness,
            self.evidence_traceability,
        )
        if self.success and (self.failure_code is not None or any(v != 1 for v in quality)):
            raise ValueError("successful evaluation case is inconsistent")
        if not self.success and self.failure_code is None:
            raise ValueError("failed evaluation case requires a failure code")
        return self


class EvaluationMetrics(_EvaluationModel):
    routing_accuracy: float = Field(ge=0, le=1, allow_inf_nan=False)
    agent_success_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    report_completeness: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_traceability: float = Field(ge=0, le=1, allow_inf_nan=False)
    average_latency_ms: float = Field(ge=0, allow_inf_nan=False)
    max_latency_ms: float = Field(ge=0, allow_inf_nan=False)
    agent_latency_status: AgentLatencyStatus = "unavailable"


class EvaluationFailure(_EvaluationModel):
    case_id: str
    code: EvaluationFailureCode


class EvaluationSummary(_EvaluationModel):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "EvaluationSummary":
        if self.total != self.passed + self.failed:
            raise ValueError("evaluation summary counts are inconsistent")
        return self


class EvaluationReport(_EvaluationModel):
    version: str
    dataset: str
    cases: tuple[EvaluationCaseResult, ...]
    metrics: EvaluationMetrics
    failures: tuple[EvaluationFailure, ...]
    summary: EvaluationSummary

    @field_validator("cases", "failures", mode="before")
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("metrics", "summary", mode="before")
    @classmethod
    def isolate_models(cls, value: object) -> object:
        return copy.deepcopy(value)

    @model_validator(mode="after")
    def validate_report(self) -> "EvaluationReport":
        identifiers = [case.case_id.casefold() for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evaluation case identifiers must be unique")
        passed = sum(case.success for case in self.cases)
        if self.summary != EvaluationSummary(
            total=len(self.cases),
            passed=passed,
            failed=len(self.cases) - passed,
        ):
            raise ValueError("evaluation report summary is inconsistent")
        expected_failures = {
            (case.case_id.casefold(), case.failure_code)
            for case in self.cases
            if not case.success
        }
        actual_failures = {
            (failure.case_id.casefold(), failure.code) for failure in self.failures
        }
        if len(actual_failures) != len(self.failures) or actual_failures != expected_failures:
            raise ValueError("evaluation report failures are inconsistent")
        return self
