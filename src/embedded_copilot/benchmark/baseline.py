from __future__ import annotations

import hashlib
import json

from embedded_copilot.benchmark.models import BenchmarkBaseline, BenchmarkReport


CURRENT_BASELINE_SCHEMA_VERSION = 1


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def metrics_snapshot_hash(metrics: dict[str, float]) -> str:
    return _canonical_hash(metrics)


def report_snapshot(report: BenchmarkReport) -> tuple[str, str, dict[str, float]]:
    validated = BenchmarkReport.model_validate(report.model_dump(mode="json"))
    metrics = dict(validated.metrics)
    metrics["average_score"] = validated.average_score
    return (
        _canonical_hash(validated.model_dump(mode="json")),
        metrics_snapshot_hash(metrics),
        metrics,
    )


def create_baseline(
    *,
    benchmark_version: str,
    evaluated_project_version: str,
    report: BenchmarkReport,
) -> BenchmarkBaseline:
    report_hash, metrics_hash, metrics = report_snapshot(report)
    return BenchmarkBaseline(
        benchmark_version=benchmark_version,
        evaluated_project_version=evaluated_project_version,
        schema_version=CURRENT_BASELINE_SCHEMA_VERSION,
        report_hash=report_hash,
        metrics_hash=metrics_hash,
        metrics=metrics,
    )
