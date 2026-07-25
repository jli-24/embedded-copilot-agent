from __future__ import annotations

import copy

from embedded_copilot.evaluation.models import (
    EvaluationCaseResult,
    EvaluationFailure,
    EvaluationMetrics,
    EvaluationReport,
    EvaluationSummary,
)


def _average(cases: tuple[EvaluationCaseResult, ...], field: str) -> float:
    return sum(float(getattr(case, field)) for case in cases) / len(cases)


def build_evaluation_report(
    *,
    version: str,
    dataset: str,
    cases: tuple[EvaluationCaseResult, ...],
) -> EvaluationReport:
    isolated = tuple(copy.deepcopy(cases))
    if not isolated:
        raise ValueError("evaluation cases are empty")
    passed = sum(case.success for case in isolated)
    failures = tuple(
        EvaluationFailure(case_id=case.case_id, code=case.failure_code)
        for case in isolated
        if not case.success and case.failure_code is not None
    )
    return EvaluationReport(
        version=version,
        dataset=dataset,
        cases=isolated,
        metrics=EvaluationMetrics(
            routing_accuracy=_average(isolated, "routing_accuracy"),
            agent_success_rate=_average(isolated, "agent_success_rate"),
            report_completeness=_average(isolated, "report_completeness"),
            evidence_traceability=_average(isolated, "evidence_traceability"),
            average_latency_ms=round(
                _average(isolated, "execution_latency_ms"),
                6,
            ),
            max_latency_ms=round(
                max(case.execution_latency_ms for case in isolated),
                6,
            ),
        ),
        failures=failures,
        summary=EvaluationSummary(
            total=len(isolated),
            passed=passed,
            failed=len(isolated) - passed,
        ),
    )
