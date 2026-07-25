from __future__ import annotations

from embedded_copilot.evaluation.models import EvaluationCaseResult
from embedded_copilot.evaluation.report import build_evaluation_report


def _case(
    case_id: str,
    *,
    success: bool,
    quality: float,
    latency: float,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id=case_id,
        success=success,
        routing_accuracy=quality,
        agent_success_rate=quality,
        report_completeness=quality,
        evidence_traceability=quality,
        execution_latency_ms=latency,
        failure_code=None if success else "evaluation_failed",
    )


def test_report_builder_aggregates_cases_in_stable_order() -> None:
    cases = (
        _case("case-1", success=True, quality=1.0, latency=1.1111114),
        _case("case-2", success=False, quality=0.5, latency=3.3333334),
    )

    report = build_evaluation_report(
        version="0.20.0",
        dataset="synthetic-evaluation",
        cases=cases,
    )

    assert report.cases == cases
    assert report.metrics.routing_accuracy == 0.75
    assert report.metrics.agent_success_rate == 0.75
    assert report.metrics.report_completeness == 0.75
    assert report.metrics.evidence_traceability == 0.75
    assert report.metrics.average_latency_ms == 2.222222
    assert report.metrics.max_latency_ms == 3.333333
    assert report.summary.model_dump() == {"total": 2, "passed": 1, "failed": 1}
    assert report.failures[0].model_dump() == {
        "case_id": "case-2",
        "code": "evaluation_failed",
    }
