"""Safe Product-to-Web response projections."""

from __future__ import annotations

from embedded_copilot.web_api.models import (
    WebDashboardProjection,
    WebProjectDetail,
    WebProjectReference,
    WebReportProjection,
    WebReportSection,
    WebReviewProjection,
    WebStage,
    WebStageProjection,
    WebStageStatus,
    WebTimelineEventProjection,
    WebTimelineProjection,
    web_dashboard_fingerprint,
    web_project_detail_fingerprint,
    web_project_reference_fingerprint,
    web_report_fingerprint,
    web_report_section_fingerprint,
    web_review_fingerprint,
    web_stage_fingerprint,
    web_timeline_event_fingerprint,
    web_timeline_fingerprint,
)


def project_reference(workspace, session) -> WebProjectReference:
    values = dict(
        project_id=workspace.project_id,
        project_name=workspace.project_name,
        current_stage=WebStage(session.current_stage.value),
        workspace_fingerprint=workspace.fingerprint,
    )
    return WebProjectReference(
        **values, fingerprint=web_project_reference_fingerprint(**values)
    )


def project_detail(workspace, session) -> WebProjectDetail:
    reference = project_reference(workspace, session)
    values = dict(
        project=reference,
        artifact_reference_ids=tuple(
            item.reference_id for item in session.artifact_references
        ),
        execution_reference_ids=tuple(
            item.reference_id for item in session.execution_references
        ),
        feedback_reference_ids=tuple(
            item.reference_id for item in session.feedback_references
        ),
        optimization_reference_ids=tuple(
            item.reference_id for item in session.optimization_references
        ),
    )
    return WebProjectDetail(
        **values, fingerprint=web_project_detail_fingerprint(**values)
    )


def project_dashboard(workspace, dashboard) -> WebDashboardProjection:
    stages = tuple(_stage(item) for item in dashboard.stages)
    values = dict(
        project_id=workspace.project_id,
        project_name=workspace.project_name,
        current_stage=WebStage(dashboard.current_stage.value),
        overall_progress=dashboard.overall_percent,
        stages=stages,
    )
    return WebDashboardProjection(
        **values, fingerprint=web_dashboard_fingerprint(**values)
    )


def _stage(value) -> WebStageProjection:
    values = dict(
        stage=WebStage(value.stage.value),
        status=WebStageStatus(value.status.value),
        reference_ids=value.reference_ids,
    )
    return WebStageProjection(**values, fingerprint=web_stage_fingerprint(**values))


def project_timeline(workspace, timeline) -> WebTimelineProjection:
    events = tuple(_timeline_event(item) for item in timeline.events)
    values = dict(project_id=workspace.project_id, events=events)
    return WebTimelineProjection(
        **values, fingerprint=web_timeline_fingerprint(**values)
    )


def _timeline_event(value) -> WebTimelineEventProjection:
    values = dict(
        event=value.event_type.value,
        reference_id=value.reference.reference_id,
        reference_type=value.reference.reference_type.value,
        timestamp=value.timestamp,
        source_fingerprint=value.reference.source_fingerprint,
    )
    return WebTimelineEventProjection(
        **values, fingerprint=web_timeline_event_fingerprint(**values)
    )


def project_report(report) -> WebReportProjection:
    sections = tuple(_report_section(item) for item in report.sections)
    review_values = dict(
        pending_reviews=report.review_dashboard.pending_reviews,
        approved=report.review_dashboard.approved,
        rejected=report.review_dashboard.rejected,
        change_requests=report.review_dashboard.change_requests,
        reference_ids=report.review_dashboard.reference_ids,
    )
    review = WebReviewProjection(
        **review_values, fingerprint=web_review_fingerprint(**review_values)
    )
    values = dict(
        project_id=report.project_id,
        project_name=report.project_name,
        project_summary=report.project_summary,
        sections=sections,
        decision_ids=tuple(item.decision_id for item in report.decision_history),
        review=review,
        generated_at=report.generated_at,
        source_fingerprint=report.fingerprint,
    )
    return WebReportProjection(**values, fingerprint=web_report_fingerprint(**values))


def _report_section(value) -> WebReportSection:
    values = dict(
        stage=WebStage(value.stage.value),
        status=WebStageStatus(value.status.value),
        reference_ids=value.reference_ids,
        source_fingerprints=value.source_fingerprints,
    )
    return WebReportSection(
        **values, fingerprint=web_report_section_fingerprint(**values)
    )
