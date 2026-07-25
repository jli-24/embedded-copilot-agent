"""Offline evaluation of existing Embedded Copilot workflows."""

from embedded_copilot.evaluation.models import (
    EvaluationCaseResult,
    EvaluationFailure,
    EvaluationMetrics,
    EvaluationReport,
    EvaluationSummary,
)
from embedded_copilot.evaluation.renderer import (
    render_evaluation_json,
    render_evaluation_markdown,
)
from embedded_copilot.evaluation.runner import EvaluationRunner
from embedded_copilot.evaluation.scenarios import create_default_evaluation_dataset


__all__ = [
    "EvaluationCaseResult",
    "EvaluationFailure",
    "EvaluationMetrics",
    "EvaluationReport",
    "EvaluationRunner",
    "EvaluationSummary",
    "create_default_evaluation_dataset",
    "render_evaluation_json",
    "render_evaluation_markdown",
]
