import embedded_copilot.integration as integration

from embedded_copilot.integration import (
    AgentExecutionResult,
    EngineeringContext,
    EngineeringReport,
    IntegrationPlanner,
    IntegrationTraceEvent,
    ResultAggregator,
    render_report_json,
    render_report_markdown,
)


def test_integration_package_exports_stable_public_contracts() -> None:
    assert AgentExecutionResult.__name__ == "AgentExecutionResult"
    assert EngineeringContext.__name__ == "EngineeringContext"
    assert EngineeringReport.__name__ == "EngineeringReport"
    assert IntegrationPlanner.__name__ == "IntegrationPlanner"
    assert IntegrationTraceEvent.__name__ == "IntegrationTraceEvent"
    assert ResultAggregator.__name__ == "ResultAggregator"
    assert callable(render_report_json)
    assert callable(render_report_markdown)


def test_integration_package_does_not_export_executor_orchestration() -> None:
    assert not hasattr(integration, "AgentExecutor")
