from __future__ import annotations

import copy
import json

from embedded_copilot.evaluation.models import EvaluationReport


def _validated(report: EvaluationReport) -> EvaluationReport:
    return EvaluationReport.model_validate(
        copy.deepcopy(report.model_dump(mode="python"))
    )


def render_evaluation_json(report: EvaluationReport) -> str:
    validated = _validated(report)
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def render_evaluation_markdown(report: EvaluationReport) -> str:
    validated = _validated(report)
    metrics = validated.metrics
    lines = [
        "# Embedded Copilot Evaluation",
        "",
        "## Summary",
        "",
        f"- Version: {validated.version}",
        f"- Dataset: {validated.dataset}",
        f"- Total: {validated.summary.total}",
        f"- Passed: {validated.summary.passed}",
        f"- Failed: {validated.summary.failed}",
        "",
        "## Metrics",
        "",
        f"- Task routing accuracy: {metrics.routing_accuracy:.6f}",
        f"- Agent success rate: {metrics.agent_success_rate:.6f}",
        f"- Report completeness: {metrics.report_completeness:.6f}",
        f"- Evidence traceability: {metrics.evidence_traceability:.6f}",
        f"- Average total latency: {metrics.average_latency_ms:.6f} ms",
        f"- Maximum total latency: {metrics.max_latency_ms:.6f} ms",
        f"- Agent latency: {metrics.agent_latency_status}",
        "",
        "## Cases",
        "",
    ]
    for case in validated.cases:
        lines.append(
            f"- {case.case_id}: {'passed' if case.success else 'failed'}; "
            f"total_latency_ms={case.execution_latency_ms:.6f}; "
            f"agent_latency={case.agent_latency_status}"
        )
    lines.extend(["", "## Failures", ""])
    if validated.failures:
        lines.extend(
            f"- {failure.case_id}: {failure.code}"
            for failure in validated.failures
        )
    else:
        lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"
