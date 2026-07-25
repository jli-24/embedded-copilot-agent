from __future__ import annotations

import json

from embedded_copilot.evaluation.models import EvaluationCaseResult
from embedded_copilot.evaluation.renderer import (
    render_evaluation_json,
    render_evaluation_markdown,
)
from embedded_copilot.evaluation.report import build_evaluation_report


def _report():
    case = EvaluationCaseResult(
        case_id="case-1",
        success=True,
        routing_accuracy=1.0,
        agent_success_rate=1.0,
        report_completeness=1.0,
        evidence_traceability=1.0,
        execution_latency_ms=1.25,
    )
    return build_evaluation_report(
        version="0.20.0",
        dataset="synthetic-evaluation",
        cases=(case,),
    )


def test_json_renderer_is_deterministic_and_has_stable_top_level_order() -> None:
    first = render_evaluation_json(_report())
    second = render_evaluation_json(_report())

    assert first == second
    assert first.endswith("\n") and not first.endswith("\n\n")
    assert tuple(json.loads(first)) == (
        "version",
        "dataset",
        "cases",
        "metrics",
        "failures",
        "summary",
    )
    assert '\n  "version"' in first


def test_markdown_renderer_has_fixed_safe_section_order() -> None:
    rendered = render_evaluation_markdown(_report())

    headings = [line for line in rendered.splitlines() if line.startswith("## ")]
    assert headings == ["## Summary", "## Metrics", "## Cases", "## Failures"]
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
