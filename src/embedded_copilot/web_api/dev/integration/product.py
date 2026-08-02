"""Safe deterministic Product integration for local Web development."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.product import (
    CreateProjectRequest,
    DashboardStageProjection,
    EngineeringDashboardProjection,
    EngineeringReleaseReport,
    EngineeringReleaseSection,
    EngineeringTimelineEvent,
    EngineeringTimelineProjection,
    EngineeringWorkspace,
    ProductReference,
    ProductReferenceType,
    ProductStage,
    ProductStageReference,
    ProductStageStatus,
    ProductTimelineEventType,
    ProjectSession,
    ReviewDashboardProjection,
    dashboard_stage_fingerprint,
    engineering_dashboard_fingerprint,
    engineering_release_report_fingerprint,
    engineering_workspace_fingerprint,
    product_reference_fingerprint,
    product_stage_reference_fingerprint,
    project_session_fingerprint,
    release_section_fingerprint,
    review_dashboard_fingerprint,
    timeline_event_fingerprint,
    timeline_projection_fingerprint,
)


class DemoProductWorkspacePort:
    """Implement ProductWorkspacePort with immutable in-memory projections."""

    __slots__ = ()

    def create_project(self, request: CreateProjectRequest) -> EngineeringWorkspace:
        checked = _typed_copy(request, CreateProjectRequest)
        reference = _requirement_reference(checked)
        stages = tuple(
            _stage(
                stage,
                _stage_status(stage),
                (reference,) if stage is ProductStage.REQUIREMENT else (),
            )
            for stage in ProductStage
        )
        session = _session(checked)
        timeline = _timeline(reference, checked.created_at)
        review = _review()
        values = dict(
            project_id=checked.project_id,
            project_name=checked.project_name,
            project_summary=checked.project_summary,
            session=session,
            stage_references=stages,
            timeline=timeline,
            decisions=(),
            review_dashboard=review,
            created_at=checked.created_at,
        )
        return EngineeringWorkspace(
            **values,
            fingerprint=engineering_workspace_fingerprint(**values),
        )

    def get_project(self, workspace: EngineeringWorkspace) -> ProjectSession:
        checked = _typed_copy(workspace, EngineeringWorkspace)
        return _typed_copy(checked.session, ProjectSession)

    def get_progress(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringDashboardProjection:
        checked = _typed_copy(workspace, EngineeringWorkspace)
        stages = tuple(_dashboard_stage(item) for item in checked.stage_references)
        values = dict(
            project_id=checked.project_id,
            current_stage=checked.session.current_stage,
            stages=stages,
            completed_count=1,
            blocked_count=0,
            overall_percent=100.0 / len(ProductStage),
            workspace_fingerprint=checked.fingerprint,
        )
        return EngineeringDashboardProjection(
            **values,
            fingerprint=engineering_dashboard_fingerprint(**values),
        )

    def generate_report(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringReleaseReport:
        checked = _typed_copy(workspace, EngineeringWorkspace)
        sections = tuple(_release_section(item) for item in checked.stage_references)
        values = dict(
            project_id=checked.project_id,
            project_name=checked.project_name,
            project_summary=checked.project_summary,
            workspace_fingerprint=checked.fingerprint,
            sections=sections,
            decision_history=(),
            review_dashboard=checked.review_dashboard,
            generated_at=checked.created_at,
        )
        return EngineeringReleaseReport(
            **values,
            fingerprint=engineering_release_report_fingerprint(**values),
        )


def _requirement_reference(request: CreateProjectRequest) -> ProductReference:
    values = dict(
        reference_type=ProductReferenceType.REQUIREMENT,
        reference_id="demo-requirement",
        source_fingerprint=request.fingerprint,
    )
    return ProductReference(
        **values,
        fingerprint=product_reference_fingerprint(**values),
    )


def _stage_status(stage: ProductStage) -> ProductStageStatus:
    if stage is ProductStage.REQUIREMENT:
        return ProductStageStatus.COMPLETED
    if stage is ProductStage.ARCHITECTURE:
        return ProductStageStatus.IN_PROGRESS
    return ProductStageStatus.NOT_STARTED


def _stage(
    stage: ProductStage,
    status: ProductStageStatus,
    references: tuple[ProductReference, ...],
) -> ProductStageReference:
    values = dict(stage=stage, status=status, references=references)
    return ProductStageReference(
        **values,
        fingerprint=product_stage_reference_fingerprint(**values),
    )


def _session(request: CreateProjectRequest) -> ProjectSession:
    values = dict(
        project_id=request.project_id,
        session_id=request.session_id,
        current_stage=ProductStage.ARCHITECTURE,
        artifact_references=(),
        execution_references=(),
        feedback_references=(),
        optimization_references=(),
    )
    return ProjectSession(
        **values,
        fingerprint=project_session_fingerprint(**values),
    )


def _timeline(reference: ProductReference, timestamp) -> EngineeringTimelineProjection:
    event_values = dict(
        event_type=ProductTimelineEventType.REQUIREMENT_COMPLETED,
        reference=reference,
        timestamp=timestamp,
    )
    event = EngineeringTimelineEvent(
        **event_values,
        fingerprint=timeline_event_fingerprint(**event_values),
    )
    values = dict(events=(event,))
    return EngineeringTimelineProjection(
        **values,
        fingerprint=timeline_projection_fingerprint(**values),
    )


def _review() -> ReviewDashboardProjection:
    values = dict(
        pending_reviews=0,
        approved=0,
        rejected=0,
        change_requests=0,
        reference_ids=(),
    )
    return ReviewDashboardProjection(
        **values,
        fingerprint=review_dashboard_fingerprint(**values),
    )


def _dashboard_stage(stage: ProductStageReference) -> DashboardStageProjection:
    values = dict(
        stage=stage.stage,
        status=stage.status,
        reference_ids=tuple(item.reference_id for item in stage.references),
    )
    return DashboardStageProjection(
        **values,
        fingerprint=dashboard_stage_fingerprint(**values),
    )


def _release_section(stage: ProductStageReference) -> EngineeringReleaseSection:
    values = dict(
        stage=stage.stage,
        status=stage.status,
        reference_ids=tuple(item.reference_id for item in stage.references),
        source_fingerprints=tuple(item.source_fingerprint for item in stage.references),
    )
    return EngineeringReleaseSection(
        **values,
        fingerprint=release_section_fingerprint(**values),
    )


def _typed_copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise TypeError("typed demo projection is required")
    try:
        return expected_type.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise ValueError("demo projection is invalid") from None
