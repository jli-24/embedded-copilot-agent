"""Stateless Engineering Intelligence orchestration."""

from __future__ import annotations

from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceRejected,
)
from embedded_copilot.engineering_intelligence.knowledge.fusion import (
    build_engineering_context,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringContextRequest,
    EngineeringContextSnapshot,
    EngineeringIntelligenceProgressEvent,
    EngineeringIntelligenceRequest,
    EngineeringIntelligenceSnapshot,
    EngineeringIntelligenceStage,
    EngineeringProgressStatus,
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
    EngineeringRequirementRequest,
    intelligence_snapshot_fingerprint,
    progress_event_fingerprint,
)
from embedded_copilot.engineering_intelligence.planning.agent import _PlanningAgent
from embedded_copilot.engineering_intelligence.requirement.agent import (
    _RequirementAgent,
)


class _EngineeringIntelligenceService:
    def __init__(self) -> None:
        self._requirement_agent = _RequirementAgent()
        self._planning_agent = _PlanningAgent()

    def analyze_requirement(
        self,
        request: EngineeringRequirementRequest,
    ) -> EngineeringRequirementDocument:
        try:
            return self._requirement_agent.analyze(request)
        except Exception:
            raise EngineeringIntelligenceRejected(
                "intelligence request rejected"
            ) from None

    def create_plan(
        self,
        requirement: EngineeringRequirementDocument,
    ) -> EngineeringProjectPlan:
        try:
            return self._planning_agent.plan(requirement)
        except Exception:
            raise EngineeringIntelligenceRejected(
                "intelligence request rejected"
            ) from None

    def build_context(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextSnapshot:
        try:
            return build_engineering_context(request)
        except Exception:
            raise EngineeringIntelligenceRejected(
                "intelligence request rejected"
            ) from None

    def prepare_project(
        self,
        request: EngineeringIntelligenceRequest,
    ) -> EngineeringIntelligenceSnapshot:
        try:
            checked = _typed_copy(request, EngineeringIntelligenceRequest)
            requirement = self._requirement_agent.analyze(
                EngineeringRequirementRequest(
                    project=checked.project,
                    session_id=checked.session_id,
                    message_id=checked.message_id,
                    requirement_summary=checked.requirement_summary,
                    requested_at=checked.requested_at,
                )
            )
            plan = self._planning_agent.plan(requirement)
            context = build_engineering_context(
                EngineeringContextRequest(
                    project=checked.project,
                    requirement=requirement,
                    plan=plan,
                    evidence=checked.evidence,
                    requested_at=checked.requested_at,
                )
            )
            progress = _progress_events(
                project_id=checked.project.project_id,
                session_id=checked.session_id,
                requirement_count=(
                    len(requirement.functional_requirements)
                    + len(requirement.hardware_constraints)
                ),
                task_count=len(plan.tasks),
                evidence_count=len(context.evidence),
                timestamp=checked.requested_at,
            )
            values = dict(
                project=checked.project,
                requirement=requirement,
                plan=plan,
                context=context,
                progress_events=progress,
            )
            return EngineeringIntelligenceSnapshot(
                **values,
                fingerprint=intelligence_snapshot_fingerprint(**values),
            )
        except EngineeringIntelligenceRejected:
            raise
        except Exception:
            raise EngineeringIntelligenceRejected(
                "intelligence request rejected"
            ) from None


def _progress_events(
    *,
    project_id: str,
    session_id: str,
    requirement_count: int,
    task_count: int,
    evidence_count: int,
    timestamp,
) -> tuple[EngineeringIntelligenceProgressEvent, ...]:
    definitions = (
        (EngineeringIntelligenceStage.REQUIREMENT, 0.0, 0),
        (EngineeringIntelligenceStage.REQUIREMENT, 1.0, requirement_count),
        (EngineeringIntelligenceStage.PLANNING, 0.0, 0),
        (EngineeringIntelligenceStage.PLANNING, 1.0, task_count),
        (EngineeringIntelligenceStage.KNOWLEDGE, 0.0, 0),
        (EngineeringIntelligenceStage.KNOWLEDGE, 1.0, evidence_count),
    )
    events = []
    for sequence, (stage, progress, count) in enumerate(definitions, start=1):
        status = (
            EngineeringProgressStatus.STARTED
            if progress == 0.0
            else EngineeringProgressStatus.COMPLETED
        )
        values = dict(
            sequence=sequence,
            project_id=project_id,
            session_id=session_id,
            stage=stage,
            status=status,
            progress=progress,
            count=count,
            timestamp=timestamp,
        )
        events.append(
            EngineeringIntelligenceProgressEvent(
                **values,
                fingerprint=progress_event_fingerprint(**values),
            )
        )
    return tuple(events)


def _typed_copy(value: object, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed intelligence request is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)
