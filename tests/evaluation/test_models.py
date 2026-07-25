from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.evaluation.models import (
    EvaluationCaseResult,
    EvaluationFailure,
    EvaluationMetrics,
    EvaluationReport,
    EvaluationSummary,
)


def _case(*, success: bool = True) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id="case-1",
        success=success,
        routing_accuracy=1.0 if success else 0.0,
        agent_success_rate=1.0 if success else 0.0,
        report_completeness=1.0 if success else 0.0,
        evidence_traceability=1.0 if success else 0.0,
        execution_latency_ms=12.345678,
        agent_latency_status="unavailable",
        failure_code=None if success else "supervisor_execution_failed",
    )


def _metrics() -> EvaluationMetrics:
    return EvaluationMetrics(
        routing_accuracy=1.0,
        agent_success_rate=1.0,
        report_completeness=1.0,
        evidence_traceability=1.0,
        average_latency_ms=12.345678,
        max_latency_ms=12.345678,
        agent_latency_status="unavailable",
    )


def test_evaluation_models_have_exact_stable_fields() -> None:
    assert tuple(EvaluationCaseResult.model_fields) == (
        "case_id",
        "success",
        "routing_accuracy",
        "agent_success_rate",
        "report_completeness",
        "evidence_traceability",
        "execution_latency_ms",
        "agent_latency_status",
        "failure_code",
    )
    assert tuple(EvaluationReport.model_fields) == (
        "version",
        "dataset",
        "cases",
        "metrics",
        "failures",
        "summary",
    )


def test_evaluation_models_are_frozen_and_forbid_extra_fields() -> None:
    case = _case()
    with pytest.raises(ValidationError):
        case.success = False  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EvaluationSummary(total=1, passed=1, failed=0, extra=True)


def test_evaluation_models_validate_outcome_and_numeric_boundaries() -> None:
    with pytest.raises(ValidationError):
        EvaluationCaseResult(
            **{
                **_case().model_dump(mode="python"),
                "routing_accuracy": 1.1,
            }
        )
    with pytest.raises(ValidationError):
        EvaluationCaseResult(
            **{
                **_case().model_dump(mode="python"),
                "success": True,
                "failure_code": "evaluation_failed",
            }
        )
    with pytest.raises(ValidationError):
        EvaluationMetrics(
            **{
                **_metrics().model_dump(mode="python"),
                "average_latency_ms": float("inf"),
            }
        )


def test_evaluation_report_deep_copies_and_validates_nested_state() -> None:
    raw_cases = [_case()]
    report = EvaluationReport(
        version="0.20.0",
        dataset="synthetic-evaluation",
        cases=raw_cases,
        metrics=_metrics(),
        failures=[],
        summary=EvaluationSummary(total=1, passed=1, failed=0),
    )
    raw_cases.append(_case())

    assert len(report.cases) == 1
    assert report.cases[0].case_id == "case-1"


def test_evaluation_report_rejects_inconsistent_counts_and_failures() -> None:
    failed_case = _case(success=False)
    with pytest.raises(ValidationError):
        EvaluationReport(
            version="0.20.0",
            dataset="synthetic-evaluation",
            cases=(failed_case,),
            metrics=_metrics(),
            failures=(),
            summary=EvaluationSummary(total=1, passed=0, failed=1),
        )
    with pytest.raises(ValidationError):
        EvaluationSummary(total=2, passed=1, failed=0)


def test_failure_model_contains_only_safe_identifier_and_code() -> None:
    failure = EvaluationFailure(
        case_id="case-1",
        code="engineering_report_invalid",
    )
    assert failure.model_dump(mode="json") == {
        "case_id": "case-1",
        "code": "engineering_report_invalid",
    }
