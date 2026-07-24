"""Deterministic Embedded Copilot integration layer."""

from embedded_copilot.integration.aggregator import ResultAggregator
from embedded_copilot.integration.context import (
    AgentExecutionResult,
    EngineeringContext,
    IntegrationTraceEvent,
)
from embedded_copilot.integration.planner import IntegrationPlanner
from embedded_copilot.integration.report import (
    EngineeringReport,
    render_report_json,
    render_report_markdown,
)

__all__ = [
    "AgentExecutionResult",
    "EngineeringContext",
    "EngineeringReport",
    "IntegrationPlanner",
    "IntegrationTraceEvent",
    "ResultAggregator",
    "render_report_json",
    "render_report_markdown",
]
