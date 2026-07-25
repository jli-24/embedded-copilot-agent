from __future__ import annotations

import copy
from dataclasses import dataclass

from embedded_copilot.evaluation.models import (
    EvaluationCaseResult,
    EvaluationReport,
)
from embedded_copilot.evaluation.report import build_evaluation_report


@dataclass(frozen=True, slots=True)
class BenchmarkView:
    cases: int
    success_rate: float
    latency_ms: float
    coverage: float
    agent_latency_status: str


def release_benchmark_report() -> EvaluationReport:
    cases = tuple(
        EvaluationCaseResult(
            case_id=case_id,
            success=True,
            routing_accuracy=1.0,
            agent_success_rate=1.0,
            report_completeness=1.0,
            evidence_traceability=1.0,
            execution_latency_ms=latency_ms,
        )
        for case_id, latency_ms in (
            ("synthetic-esp32-camera-integration", 1.0),
            ("synthetic-firmware-debug-integration", 2.0),
            ("synthetic-pcb-review-integration", 3.0),
        )
    )
    return build_evaluation_report(
        version="0.20.0",
        dataset="synthetic-embedded-copilot-integration",
        cases=cases,
    )


def build_benchmark_view(report: EvaluationReport) -> BenchmarkView:
    validated = EvaluationReport.model_validate(
        copy.deepcopy(report.model_dump(mode="python"))
    )
    success_rate = (
        validated.summary.passed / validated.summary.total
        if validated.summary.total
        else 0.0
    )
    return BenchmarkView(
        cases=validated.summary.total,
        success_rate=success_rate,
        latency_ms=validated.metrics.average_latency_ms,
        coverage=validated.metrics.report_completeness,
        agent_latency_status=validated.metrics.agent_latency_status,
    )
