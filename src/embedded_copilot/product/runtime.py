"""Stateless aggregation and presentation projections for one project."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.product.contracts import ProductWorkspacePort
from embedded_copilot.product.exceptions import ProductProjectionRejected
from embedded_copilot.product.integration.core import CreateProjectRequest, project_core
from embedded_copilot.product.models import (
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
    project_session_fingerprint,
    product_stage_reference_fingerprint,
    release_section_fingerprint,
    review_dashboard_fingerprint,
    timeline_event_fingerprint,
    timeline_projection_fingerprint,
)

_EVENT_BY_STAGE = dict(zip(ProductStage, ProductTimelineEventType, strict=True))


class _ProductWorkspaceService(ProductWorkspacePort):
    __slots__ = ()

    def create_project(self, request: CreateProjectRequest) -> EngineeringWorkspace:
        try:
            core = project_core(request)
            stage_references = tuple(
                _stage_reference(stage, status, references)
                for stage, status, references in core.stages
            )
            current_stage = _current_stage(stage_references)
            session_values = dict(
                project_id=core.request.project_id,
                session_id=core.request.session_id,
                current_stage=current_stage,
                artifact_references=_references(
                    stage_references, ProductReferenceType.ARTIFACT
                ),
                execution_references=_references(
                    stage_references, ProductReferenceType.EXECUTION
                ),
                feedback_references=_references(
                    stage_references, ProductReferenceType.FEEDBACK
                ),
                optimization_references=_references(
                    stage_references, ProductReferenceType.OPTIMIZATION
                ),
            )
            session = ProjectSession(
                **session_values,
                fingerprint=project_session_fingerprint(**session_values),
            )
            timeline = _timeline(stage_references, core.request.created_at)
            review_values = dict(
                pending_reviews=core.pending_reviews,
                approved=core.approved,
                rejected=core.rejected,
                change_requests=core.change_requests,
                reference_ids=core.review_reference_ids,
            )
            review = ReviewDashboardProjection(
                **review_values,
                fingerprint=review_dashboard_fingerprint(**review_values),
            )
            values = dict(
                project_id=core.request.project_id,
                project_name=core.request.project_name,
                project_summary=core.request.project_summary,
                session=session,
                stage_references=stage_references,
                timeline=timeline,
                decisions=core.request.decisions,
                review_dashboard=review,
                created_at=core.request.created_at,
            )
            return EngineeringWorkspace(
                **values,
                fingerprint=engineering_workspace_fingerprint(**values),
            )
        except ProductProjectionRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise ProductProjectionRejected("product projection is invalid") from None

    def get_project(self, workspace: EngineeringWorkspace) -> ProjectSession:
        checked = _workspace(workspace)
        return ProjectSession.model_validate(checked.session.model_copy(deep=True))

    def get_progress(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringDashboardProjection:
        checked = _workspace(workspace)
        stages = tuple(_dashboard_stage(item) for item in checked.stage_references)
        completed = sum(item.status is ProductStageStatus.COMPLETED for item in stages)
        blocked = sum(item.status is ProductStageStatus.BLOCKED for item in stages)
        values = dict(
            project_id=checked.project_id,
            current_stage=checked.session.current_stage,
            stages=stages,
            completed_count=completed,
            blocked_count=blocked,
            overall_percent=completed * 100.0 / len(ProductStage),
            workspace_fingerprint=checked.fingerprint,
        )
        return EngineeringDashboardProjection(
            **values,
            fingerprint=engineering_dashboard_fingerprint(**values),
        )

    def generate_report(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringReleaseReport:
        checked = _workspace(workspace)
        sections = tuple(_release_section(item) for item in checked.stage_references)
        values = dict(
            project_id=checked.project_id,
            project_name=checked.project_name,
            project_summary=checked.project_summary,
            workspace_fingerprint=checked.fingerprint,
            sections=sections,
            decision_history=checked.decisions,
            review_dashboard=checked.review_dashboard,
            generated_at=checked.created_at,
        )
        return EngineeringReleaseReport(
            **values,
            fingerprint=engineering_release_report_fingerprint(**values),
        )


def _workspace(value: object) -> EngineeringWorkspace:
    if type(value) is not EngineeringWorkspace:
        raise ProductProjectionRejected("product projection is invalid") from None
    try:
        return EngineeringWorkspace.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise ProductProjectionRejected("product projection is invalid") from None


def _stage_reference(stage, status, references) -> ProductStageReference:
    values = dict(stage=stage, status=status, references=references)
    return ProductStageReference(
        **values,
        fingerprint=product_stage_reference_fingerprint(**values),
    )


def _current_stage(stages: tuple[ProductStageReference, ...]) -> ProductStage:
    return next(
        (
            item.stage
            for item in stages
            if item.status is not ProductStageStatus.COMPLETED
        ),
        ProductStage.OPTIMIZATION,
    )


def _references(
    stages: tuple[ProductStageReference, ...], kind: ProductReferenceType
) -> tuple[ProductReference, ...]:
    return tuple(
        reference
        for stage in stages
        for reference in stage.references
        if reference.reference_type is kind
    )


def _timeline(
    stages: tuple[ProductStageReference, ...], timestamp
) -> EngineeringTimelineProjection:
    events = []
    for stage in stages:
        if not stage.references:
            continue
        values = dict(
            event_type=_EVENT_BY_STAGE[stage.stage],
            reference=stage.references[0],
            timestamp=timestamp,
        )
        events.append(
            EngineeringTimelineEvent(
                **values,
                fingerprint=timeline_event_fingerprint(**values),
            )
        )
    event_tuple = tuple(events)
    values = dict(events=event_tuple)
    return EngineeringTimelineProjection(
        **values,
        fingerprint=timeline_projection_fingerprint(**values),
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


def _create_product_workspace_service() -> ProductWorkspacePort:
    return _ProductWorkspaceService()
