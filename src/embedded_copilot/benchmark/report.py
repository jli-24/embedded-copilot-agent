from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence

from embedded_copilot.benchmark.exceptions import BenchmarkReportError
from embedded_copilot.benchmark.metrics import PassRateMetric, ScoreAggregator
from embedded_copilot.benchmark.models import BenchmarkReport, BenchmarkResult


class BenchmarkReportBuilder:
    def build(
        self,
        name: str,
        results: Sequence[BenchmarkResult],
        *,
        trace_enabled: bool,
    ) -> BenchmarkReport:
        try:
            validated = [
                BenchmarkResult.model_validate(result.model_dump(mode="python"))
                for result in results
                if isinstance(result, BenchmarkResult)
            ]
            if not validated or len(validated) != len(results):
                raise ValueError("report requires benchmark results")
            metric_values: dict[str, list[float]] = defaultdict(list)
            categories: list[str] = []
            for result in validated:
                if set(result.metadata) != {"category", "target_name"}:
                    raise ValueError("result metadata is unsafe")
                category = result.metadata["category"]
                target_name = result.metadata["target_name"]
                if not isinstance(category, str) or not isinstance(target_name, str):
                    raise TypeError("result metadata is invalid")
                categories.append(category)
                for metric, value in result.metrics.items():
                    metric_values[metric].append(value)
            passed = sum(result.success for result in validated)
            total = len(validated)
            metrics = {
                metric: ScoreAggregator.aggregate(values)
                for metric, values in metric_values.items()
            }
            metrics["pass_rate"] = PassRateMetric.compute(passed, total)
            average = ScoreAggregator.aggregate([result.score for result in validated])
            normalized_name = name.strip()
            return BenchmarkReport(
                name=normalized_name,
                total_cases=total,
                passed_cases=passed,
                failed_cases=total - passed,
                average_score=average,
                metrics=metrics,
                results=validated,
                summary=(
                    f"Benchmark '{normalized_name}' completed {total} case(s): "
                    f"{passed} passed, {total - passed} failed; average score "
                    f"{average:.3f}."
                ),
                metadata={
                    "evaluation_mode": "deterministic_offline",
                    "category_counts": dict(Counter(categories)),
                    "trace_enabled": trace_enabled,
                },
            )
        except Exception:
            raise BenchmarkReportError("benchmark report assembly failed") from None
