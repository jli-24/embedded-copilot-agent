from __future__ import annotations

import pytest

from embedded_copilot.benchmark.baseline import (
    CURRENT_BASELINE_SCHEMA_VERSION,
)
from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError
from embedded_copilot.benchmark.models import (
    BenchmarkBaseline,
    BenchmarkReport,
    BenchmarkResult,
)
from embedded_copilot.benchmark.regression import RegressionComparator


def _report(*, score: float, extra_metrics: dict[str, float] | None = None) -> BenchmarkReport:
    result = BenchmarkResult(
        case_id="case",
        success=score == 1.0,
        score=score,
        metrics={"accuracy": score, **(extra_metrics or {})},
        errors=[] if score == 1.0 else ["metric below required score: accuracy"],
        metadata={"category": "routing", "target_name": "SupervisorAgent"},
    )
    return BenchmarkReport(
        name="suite",
        total_cases=1,
        passed_cases=int(result.success),
        failed_cases=int(not result.success),
        average_score=score,
        metrics={"accuracy": score, "pass_rate": float(result.success)},
        results=[result],
        summary="synthetic summary",
        metadata={
            "evaluation_mode": "deterministic_offline",
            "category_counts": {"routing": 1},
            "trace_enabled": True,
        },
    )


def test_baseline_hashes_canonical_report_and_metric_snapshot() -> None:
    report = _report(score=1.0)

    first = BenchmarkBaseline.from_report(
        benchmark_version="0.11.0",
        evaluated_project_version="0.11.0",
        report=report,
    )
    second = BenchmarkBaseline.from_report(
        benchmark_version="0.11.0",
        evaluated_project_version="0.11.0",
        report=report.model_copy(deep=True),
    )

    assert first == second
    assert first.schema_version == CURRENT_BASELINE_SCHEMA_VERSION
    assert len(first.report_hash) == 64
    assert len(first.metrics_hash) == 64
    assert first.metrics["average_score"] == 1.0


def test_regression_comparator_reports_metric_union_and_hashes() -> None:
    baseline = BenchmarkBaseline.from_report(
        benchmark_version="0.11.0",
        evaluated_project_version="0.10.0",
        report=_report(score=1.0),
    )

    regression = RegressionComparator.compare(baseline, _report(score=0.5))

    assert regression.regression_detected is True
    assert regression.improvement_detected is False
    assert regression.metric_delta["accuracy"] == -0.5
    assert regression.metric_delta["average_score"] == -0.5
    assert regression.baseline_report_hash == baseline.report_hash
    assert len(regression.current_metrics_hash) == 64


def test_regression_comparator_rejects_incompatible_schema() -> None:
    baseline = BenchmarkBaseline.from_report(
        benchmark_version="0.11.0",
        evaluated_project_version="0.10.0",
        report=_report(score=1.0),
    )
    incompatible = BenchmarkBaseline(
        **{
            **baseline.model_dump(mode="python"),
            "schema_version": CURRENT_BASELINE_SCHEMA_VERSION + 1,
        }
    )

    with pytest.raises(BenchmarkEvaluationError, match="schema is incompatible"):
        RegressionComparator.compare(incompatible, _report(score=1.0))


def test_regression_comparator_rejects_tampered_baseline_metrics() -> None:
    baseline = BenchmarkBaseline.from_report(
        benchmark_version="0.11.0",
        evaluated_project_version="0.10.0",
        report=_report(score=1.0),
    )
    tampered = baseline.model_copy(
        update={"metrics": {**baseline.metrics, "accuracy": 0.0}}
    )

    with pytest.raises(BenchmarkEvaluationError, match="metrics hash is invalid"):
        RegressionComparator.compare(tampered, _report(score=1.0))
