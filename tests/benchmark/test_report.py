from __future__ import annotations

import pytest

from embedded_copilot.benchmark.exceptions import BenchmarkReportError
from embedded_copilot.benchmark.models import BenchmarkResult
from embedded_copilot.benchmark.report import BenchmarkReportBuilder


def _result(
    case_id: str,
    category: str,
    score: float,
    metrics: dict[str, float],
) -> BenchmarkResult:
    success = score == 1.0 and all(value == 1.0 for value in metrics.values())
    return BenchmarkResult(
        case_id=case_id,
        success=success,
        score=score,
        metrics=metrics,
        errors=[] if success else ["metric below required score"],
        metadata={"category": category, "target_name": "SyntheticTarget"},
    )


def test_report_builder_aggregates_only_emitted_metrics_and_fixed_metadata() -> None:
    report = BenchmarkReportBuilder().build(
        " foundation ",
        [
            _result("one", "routing", 1.0, {"accuracy": 1.0}),
            _result("two", "knowledge", 0.5, {"accuracy": 0.0, "mrr": 1.0}),
        ],
        trace_enabled=True,
    )

    assert report.average_score == 0.75
    assert report.metrics == {"accuracy": 0.5, "mrr": 1.0, "pass_rate": 0.5}
    assert report.metadata == {
        "evaluation_mode": "deterministic_offline",
        "category_counts": {"routing": 1, "knowledge": 1},
        "trace_enabled": True,
    }
    assert report.summary == (
        "Benchmark 'foundation' completed 2 case(s): 1 passed, 1 failed; "
        "average score 0.750."
    )


def test_report_builder_rejects_empty_or_unsafe_result_metadata() -> None:
    with pytest.raises(BenchmarkReportError):
        BenchmarkReportBuilder().build("suite", [], trace_enabled=False)
    unsafe = _result("one", "routing", 1.0, {"accuracy": 1.0}).model_copy(
        update={"metadata": {"category": "routing", "target_name": "x", "raw": "secret"}}
    )
    with pytest.raises(BenchmarkReportError):
        BenchmarkReportBuilder().build("suite", [unsafe], trace_enabled=False)
