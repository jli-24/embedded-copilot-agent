from __future__ import annotations

from embedded_copilot.product import (
    ProductStage,
    ProductStageStatus,
    ProductTimelineEventType,
    create_product_runtime,
)
from tests.product.conftest import make_request


def test_create_project_projects_session_timeline_and_approval(product_sources) -> None:
    request = make_request(product_sources)
    before = request.model_dump(mode="json")
    port = create_product_runtime().product_workspace_port()

    workspace = port.create_project(request)

    assert port.get_project(workspace) == workspace.session
    assert workspace.project_id == "project-1"
    assert workspace.session.current_stage is ProductStage.EXECUTION
    assert workspace.session.artifact_references
    assert workspace.session.execution_references
    assert workspace.session.feedback_references
    assert workspace.session.optimization_references
    assert tuple(event.event_type for event in workspace.timeline.events) == tuple(
        ProductTimelineEventType
    )
    assert workspace.review_dashboard.change_requests == 1
    assert workspace.review_dashboard.pending_reviews >= 1
    assert request.model_dump(mode="json") == before


def test_dashboard_has_fixed_stage_order_and_progress(product_sources) -> None:
    port = create_product_runtime().product_workspace_port()
    workspace = port.create_project(make_request(product_sources))
    dashboard = port.get_progress(workspace)

    assert tuple(item.stage for item in dashboard.stages) == tuple(ProductStage)
    assert dashboard.current_stage is ProductStage.EXECUTION
    assert (
        next(
            item for item in dashboard.stages if item.stage is ProductStage.EXECUTION
        ).status
        is ProductStageStatus.BLOCKED
    )
    assert dashboard.completed_count == 8
    assert dashboard.blocked_count == 1
    assert dashboard.overall_percent == 88.88888888888889


def test_partial_project_marks_first_missing_stage_in_progress() -> None:
    request = make_request(
        {},
        requirement=None,
        plan=None,
        context=None,
        hardware_proposal=None,
        firmware_proposal=None,
        validation_report=None,
        artifact_contract=None,
        execution_report=None,
        feedback_report=None,
        optimization_report=None,
        decisions=(),
    )
    port = create_product_runtime().product_workspace_port()
    dashboard = port.get_progress(port.create_project(request))
    assert dashboard.stages[0].status is ProductStageStatus.IN_PROGRESS
    assert all(
        item.status is ProductStageStatus.NOT_STARTED for item in dashboard.stages[1:]
    )


def test_release_report_aggregates_references_without_recalculation(
    product_sources,
) -> None:
    port = create_product_runtime().product_workspace_port()
    workspace = port.create_project(make_request(product_sources))
    report = port.generate_report(workspace)

    assert report.project_id == workspace.project_id
    assert report.workspace_fingerprint == workspace.fingerprint
    assert tuple(item.stage for item in report.sections) == tuple(ProductStage)
    assert report.decision_history == workspace.decisions
    assert all(item.source_fingerprints for item in report.sections)
    assert report.review_dashboard == workspace.review_dashboard
