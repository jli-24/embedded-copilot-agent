from __future__ import annotations

import copy
import math
import re
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel


BenchmarkCategory = Literal[
    "routing",
    "firmware",
    "hardware",
    "pcb",
    "debug",
    "knowledge",
    "end_to_end",
]

TraceEventType = Literal["agent_call", "knowledge_call", "handoff"]
TraceStatus = Literal["success", "error"]
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _copy_mapping(value: object) -> object:
    return copy.deepcopy(value)


def _normalize_strings(values: object) -> object:
    if not isinstance(values, Sequence) or isinstance(
        values, (str, bytes, bytearray)
    ):
        return values
    result: list[object] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip() if isinstance(value, str) else value
        if isinstance(candidate, str):
            if not candidate:
                raise ValueError("list values must not be empty")
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
        result.append(candidate)
    return result


def _validate_metrics(value: object) -> object:
    if not isinstance(value, dict):
        return value
    copied = copy.deepcopy(value)
    for name, score in copied.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("metric names must be non-empty strings")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("metric values must be numbers")
        if not math.isfinite(float(score)) or not 0 <= float(score) <= 1:
            raise ValueError("metric values must be between zero and one")
    return {name.strip(): float(score) for name, score in copied.items()}


class BenchmarkCase(ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: BenchmarkCategory
    input: str = Field(min_length=1)
    expected: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id", "name", "category", "input", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("expected", "metadata", mode="before")
    @classmethod
    def isolate_mappings(cls, value: object) -> object:
        return _copy_mapping(value)


class BenchmarkResult(ContractModel):
    case_id: str = Field(min_length=1)
    success: bool
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    metrics: dict[str, float] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("case_id", mode="before")
    @classmethod
    def strip_case_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, value: object) -> object:
        return _validate_metrics(value)

    @field_validator("errors", mode="before")
    @classmethod
    def normalize_errors(cls, value: object) -> object:
        return _normalize_strings(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def isolate_metadata(cls, value: object) -> object:
        return _copy_mapping(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> "BenchmarkResult":
        if self.success and self.errors:
            raise ValueError("successful benchmark results cannot contain errors")
        if not self.success and not self.errors:
            raise ValueError("failed benchmark results require at least one error")
        if not set(self.metadata).issubset({"category", "target_name"}):
            raise ValueError("benchmark result metadata contains forbidden keys")
        return self


class BenchmarkReport(ContractModel):
    name: str = Field(min_length=1)
    total_cases: int = Field(ge=1)
    passed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    average_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    metrics: dict[str, float] = Field(default_factory=dict)
    results: list[BenchmarkResult] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("name", "summary", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, value: object) -> object:
        return _validate_metrics(value)

    @field_validator("results", "metadata", mode="before")
    @classmethod
    def isolate_nested_values(cls, value: object) -> object:
        return copy.deepcopy(value)

    @model_validator(mode="after")
    def validate_report(self) -> "BenchmarkReport":
        if not set(self.metadata).issubset(
            {"evaluation_mode", "category_counts", "trace_enabled"}
        ):
            raise ValueError("benchmark report metadata contains forbidden keys")
        if self.total_cases != len(self.results):
            raise ValueError("total cases must match result count")
        if self.total_cases != self.passed_cases + self.failed_cases:
            raise ValueError("case counts are inconsistent")
        if self.passed_cases != sum(result.success for result in self.results):
            raise ValueError("passed cases must match successful results")
        identifiers = [result.case_id.casefold() for result in self.results]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate benchmark result case ids are not allowed")
        expected_average = sum(result.score for result in self.results) / len(
            self.results
        )
        if not math.isclose(self.average_score, expected_average, abs_tol=1e-12):
            raise ValueError("average score must match benchmark results")
        return self


class ExecutionMetrics(ContractModel):
    execution_time_ms: float = Field(ge=0, allow_inf_nan=False)
    agent_calls: int = Field(ge=0)
    knowledge_calls: int = Field(ge=0)


class TraceEvent(ContractModel):
    sequence: int = Field(ge=1)
    event_type: TraceEventType
    target: str = Field(min_length=1)
    status: TraceStatus
    handoff_from: str | None = Field(default=None, min_length=1)
    handoff_to: str | None = Field(default=None, min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "event_type",
        "target",
        "status",
        "handoff_from",
        "handoff_to",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("metadata", mode="before")
    @classmethod
    def isolate_metadata(cls, value: object) -> object:
        return _copy_mapping(value)

    @model_validator(mode="after")
    def validate_handoff(self) -> "TraceEvent":
        has_handoff = self.handoff_from is not None or self.handoff_to is not None
        if self.event_type == "handoff" and (
            self.handoff_from is None or self.handoff_to is None
        ):
            raise ValueError("handoff events require source and destination")
        if self.event_type != "handoff" and has_handoff:
            raise ValueError("call events cannot contain handoff endpoints")
        return self


class BenchmarkTrace(ContractModel):
    case_id: str = Field(min_length=1)
    events: list[TraceEvent] = Field(default_factory=list)
    execution_metrics: ExecutionMetrics

    @field_validator("case_id", mode="before")
    @classmethod
    def strip_case_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("events", mode="before")
    @classmethod
    def isolate_events(cls, value: object) -> object:
        return copy.deepcopy(value)

    @model_validator(mode="after")
    def validate_sequence(self) -> "BenchmarkTrace":
        if [event.sequence for event in self.events] != list(
            range(1, len(self.events) + 1)
        ):
            raise ValueError("trace event sequence must be contiguous")
        return self


class BenchmarkBaseline(ContractModel):
    benchmark_version: str = Field(min_length=1)
    evaluated_project_version: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    report_hash: str
    metrics_hash: str
    metrics: dict[str, float]

    @field_validator(
        "benchmark_version",
        "evaluated_project_version",
        "report_hash",
        "metrics_hash",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("report_hash", "metrics_hash")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("benchmark hashes must be lowercase SHA-256 values")
        return value

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, value: object) -> object:
        return _validate_metrics(value)

    @classmethod
    def from_report(
        cls,
        *,
        benchmark_version: str,
        evaluated_project_version: str,
        report: "BenchmarkReport",
    ) -> "BenchmarkBaseline":
        from embedded_copilot.benchmark.baseline import create_baseline

        return create_baseline(
            benchmark_version=benchmark_version,
            evaluated_project_version=evaluated_project_version,
            report=report,
        )


class RegressionReport(ContractModel):
    benchmark_version: str = Field(min_length=1)
    evaluated_project_version: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    baseline_report_hash: str
    current_report_hash: str
    baseline_metrics_hash: str
    current_metrics_hash: str
    metric_delta: dict[str, float]
    regression_detected: bool
    improvement_detected: bool
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "benchmark_version",
        "evaluated_project_version",
        "baseline_report_hash",
        "current_report_hash",
        "baseline_metrics_hash",
        "current_metrics_hash",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "baseline_report_hash",
        "current_report_hash",
        "baseline_metrics_hash",
        "current_metrics_hash",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("benchmark hashes must be lowercase SHA-256 values")
        return value

    @field_validator("metric_delta", mode="before")
    @classmethod
    def validate_delta(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        result: dict[str, float] = {}
        for name, delta in copy.deepcopy(value).items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("metric delta names must be non-empty strings")
            if isinstance(delta, bool) or not isinstance(delta, (int, float)):
                raise ValueError("metric deltas must be numbers")
            candidate = float(delta)
            if not math.isfinite(candidate) or not -1 <= candidate <= 1:
                raise ValueError("metric deltas must be between minus one and one")
            result[name.strip()] = candidate
        return result

    @field_validator("metadata", mode="before")
    @classmethod
    def isolate_metadata(cls, value: object) -> object:
        return _copy_mapping(value)
