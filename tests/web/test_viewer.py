from __future__ import annotations

from embedded_copilot.integration.context import IntegrationTraceEvent
from embedded_copilot.integration.report import EngineeringReport, ReportSummary
from web.viewer import build_report_view


def test_viewer_projects_only_engineering_report_fields() -> None:
    source_id = "supervisor:engineering-report"
    report = EngineeringReport(
        summary=ReportSummary(
            text="Execution completed.",
            succeeded=0,
            failed=0,
            source_agent="SupervisorAgent",
            source_id=source_id,
        ),
        trace=(
            IntegrationTraceEvent(
                sequence=1,
                stage="report_aggregated",
                status="success",
                source_agent="SupervisorAgent",
                source_id=source_id,
            ),
        ),
    )

    view = build_report_view(report)

    assert view.summary["source_agent"] == "SupervisorAgent"
    assert view.trace == (
        {
            "sequence": 1,
            "stage": "report_aggregated",
            "status": "success",
            "source_agent": "SupervisorAgent",
            "source_id": source_id,
        },
    )
