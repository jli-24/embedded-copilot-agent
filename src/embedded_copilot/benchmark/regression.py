from __future__ import annotations

from embedded_copilot.benchmark.baseline import (
    CURRENT_BASELINE_SCHEMA_VERSION,
    metrics_snapshot_hash,
    report_snapshot,
)
from embedded_copilot.benchmark.exceptions import BenchmarkEvaluationError
from embedded_copilot.benchmark.models import (
    BenchmarkBaseline,
    BenchmarkReport,
    RegressionReport,
)


class RegressionComparator:
    @staticmethod
    def compare(
        baseline: BenchmarkBaseline,
        current_report: BenchmarkReport,
    ) -> RegressionReport:
        validated = BenchmarkBaseline.model_validate(
            baseline.model_dump(mode="json")
        )
        if validated.schema_version != CURRENT_BASELINE_SCHEMA_VERSION:
            raise BenchmarkEvaluationError("benchmark baseline schema is incompatible")
        if metrics_snapshot_hash(validated.metrics) != validated.metrics_hash:
            raise BenchmarkEvaluationError(
                "benchmark baseline metrics hash is invalid"
            )
        current_report_hash, current_metrics_hash, current_metrics = report_snapshot(
            current_report
        )
        metric_names = sorted(set(validated.metrics).union(current_metrics))
        delta = {
            name: current_metrics.get(name, 0.0) - validated.metrics.get(name, 0.0)
            for name in metric_names
        }
        tolerance = 1e-12
        return RegressionReport(
            benchmark_version=validated.benchmark_version,
            evaluated_project_version=validated.evaluated_project_version,
            schema_version=validated.schema_version,
            baseline_report_hash=validated.report_hash,
            current_report_hash=current_report_hash,
            baseline_metrics_hash=validated.metrics_hash,
            current_metrics_hash=current_metrics_hash,
            metric_delta=delta,
            regression_detected=any(value < -tolerance for value in delta.values()),
            improvement_detected=any(value > tolerance for value in delta.values()),
        )
