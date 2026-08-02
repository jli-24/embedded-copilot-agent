from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from embedded_copilot.workflow_runtime.approval.service import (
    validate_workflow_approval,
)
from embedded_copilot.workflow_runtime.contracts import (
    EngineeringPlanningAgentPort,
    EngineeringWorkflowPort,
    RequirementAgentPort,
    WorkflowContextPort,
    WorkflowProgressSink,
)
from embedded_copilot.workflow_runtime.dag.service import build_task_dag
from embedded_copilot.workflow_runtime.exceptions import (
    WorkflowAgentUnavailable,
    WorkflowApprovalRejected,
    WorkflowContextUnavailable,
    WorkflowDAGRejected,
    WorkflowProgressUnavailable,
    WorkflowRiskRejected,
)
from embedded_copilot.workflow_runtime.models import (
    EngineeringPlanningRequest,
    EngineeringWorkflowPlan,
    FrozenTaskDAG,
    FrozenWorkflowSnapshot,
    RequirementAgentRequest,
    RequirementSpecification,
    WorkflowApprovalContext,
    WorkflowApprovalDecision,
    WorkflowContextProjection,
    WorkflowContextRequest,
    WorkflowPreparationRequest,
    WorkflowProgressEvent,
    WorkflowProgressEventType,
    WorkflowRiskProjection,
    WorkflowScheduleBatch,
    WorkflowState,
    workflow_snapshot_fingerprint,
)
from embedded_copilot.workflow_runtime.risk.projection import project_workflow_risks
from embedded_copilot.workflow_runtime.scheduler.service import build_schedule

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _typed_copy(value: object, expected_type: type[_ModelT]) -> _ModelT:
    if type(value) is not expected_type:
        raise TypeError("typed workflow value is invalid")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)


def _snapshot(
    *,
    state: WorkflowState,
    requirements: RequirementSpecification,
    context: WorkflowContextProjection,
    risks: WorkflowRiskProjection,
    plan: EngineeringWorkflowPlan,
    dag: FrozenTaskDAG,
    schedule: tuple[WorkflowScheduleBatch, ...],
    progress_sequence: int,
) -> FrozenWorkflowSnapshot:
    fingerprint = workflow_snapshot_fingerprint(
        workflow_id=requirements.workflow_id,
        state=state,
        requirements=requirements,
        context=context,
        risks=risks,
        plan=plan,
        dag=dag,
        schedule=schedule,
        progress_sequence=progress_sequence,
    )
    return FrozenWorkflowSnapshot(
        workflow_id=requirements.workflow_id,
        state=state,
        requirements=requirements,
        context=context,
        risks=risks,
        plan=plan,
        dag=dag,
        schedule=schedule,
        progress_sequence=progress_sequence,
        fingerprint=fingerprint,
    )


class _EngineeringWorkflowService:
    __slots__ = (
        "_context_port",
        "_planning_agent",
        "_progress_sink",
        "_requirement_agent",
    )

    def __init__(
        self,
        *,
        requirement_agent: RequirementAgentPort,
        planning_agent: EngineeringPlanningAgentPort,
        context_port: WorkflowContextPort,
        progress_sink: WorkflowProgressSink,
    ) -> None:
        self._requirement_agent = requirement_agent
        self._planning_agent = planning_agent
        self._context_port = context_port
        self._progress_sink = progress_sink

    def _emit(
        self,
        *,
        sequence: int,
        workflow_id: str,
        event: WorkflowProgressEventType,
        state: WorkflowState,
        count: int,
        timestamp: datetime,
    ) -> None:
        progress = WorkflowProgressEvent(
            sequence=sequence,
            workflow_id=workflow_id,
            event=event,
            state=state,
            count=count,
            timestamp=timestamp,
        )
        try:
            self._progress_sink.emit(progress.model_copy(deep=True))
        except Exception:
            raise WorkflowProgressUnavailable(
                "workflow progress is unavailable"
            ) from None

    def _failed(
        self,
        *,
        sequence: int,
        workflow_id: str,
        count: int,
        timestamp: datetime,
    ) -> None:
        self._emit(
            sequence=sequence,
            workflow_id=workflow_id,
            event=WorkflowProgressEventType.WORKFLOW_FAILED,
            state=WorkflowState.FAILED,
            count=count,
            timestamp=timestamp,
        )

    def prepare_workflow(
        self,
        request: WorkflowPreparationRequest,
    ) -> FrozenWorkflowSnapshot:
        checked_request = _typed_copy(request, WorkflowPreparationRequest)
        sequence = 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.WORKFLOW_RECEIVED,
            state=WorkflowState.RECEIVED,
            count=0,
            timestamp=checked_request.requested_at,
        )

        try:
            raw_requirements = self._requirement_agent.analyze(
                RequirementAgentRequest(
                    workflow_id=checked_request.workflow_id,
                    requirement_summary=checked_request.requirement_summary,
                    requested_at=checked_request.requested_at,
                )
            )
            requirements = _typed_copy(
                raw_requirements,
                RequirementSpecification,
            )
            if requirements.workflow_id != checked_request.workflow_id:
                raise ValueError("workflow binding is invalid")
        except Exception:
            self._failed(
                sequence=sequence + 1,
                workflow_id=checked_request.workflow_id,
                count=0,
                timestamp=checked_request.requested_at,
            )
            raise WorkflowAgentUnavailable("requirement agent is unavailable") from None
        sequence += 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.REQUIREMENTS_READY,
            state=WorkflowState.REQUIREMENTS_READY,
            count=len(requirements.requirements),
            timestamp=checked_request.requested_at,
        )

        try:
            raw_context = self._context_port.resolve(
                WorkflowContextRequest(
                    workflow_id=checked_request.workflow_id,
                    requirement_fingerprint=requirements.fingerprint,
                )
            )
            context = _typed_copy(raw_context, WorkflowContextProjection)
            if (
                context.workflow_id != checked_request.workflow_id
                or context.requirement_fingerprint != requirements.fingerprint
            ):
                raise ValueError("context binding is invalid")
        except Exception:
            self._failed(
                sequence=sequence + 1,
                workflow_id=checked_request.workflow_id,
                count=0,
                timestamp=checked_request.requested_at,
            )
            raise WorkflowContextUnavailable(
                "workflow context is unavailable"
            ) from None
        sequence += 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.CONTEXT_PROJECTED,
            state=WorkflowState.CONTEXT_PROJECTED,
            count=len(context.verified_source_references),
            timestamp=checked_request.requested_at,
        )

        try:
            risks = project_workflow_risks(context)
        except WorkflowRiskRejected:
            self._failed(
                sequence=sequence + 1,
                workflow_id=checked_request.workflow_id,
                count=0,
                timestamp=checked_request.requested_at,
            )
            raise
        sequence += 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.RISKS_PROJECTED,
            state=WorkflowState.RISKS_PROJECTED,
            count=len(risks.risks),
            timestamp=checked_request.requested_at,
        )

        try:
            raw_plan = self._planning_agent.plan(
                EngineeringPlanningRequest(
                    requirements=requirements.model_copy(deep=True),
                    context=context.model_copy(deep=True),
                    risks=risks.model_copy(deep=True),
                )
            )
            plan = _typed_copy(raw_plan, EngineeringWorkflowPlan)
            if plan.workflow_id != checked_request.workflow_id:
                raise ValueError("plan binding is invalid")
        except Exception:
            self._failed(
                sequence=sequence + 1,
                workflow_id=checked_request.workflow_id,
                count=0,
                timestamp=checked_request.requested_at,
            )
            raise WorkflowAgentUnavailable("planning agent is unavailable") from None
        sequence += 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.PLAN_READY,
            state=WorkflowState.PLAN_READY,
            count=len(plan.tasks),
            timestamp=checked_request.requested_at,
        )

        try:
            dag = build_task_dag(plan)
        except WorkflowDAGRejected:
            self._failed(
                sequence=sequence + 1,
                workflow_id=checked_request.workflow_id,
                count=0,
                timestamp=checked_request.requested_at,
            )
            raise
        sequence += 1
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.DAG_VALIDATED,
            state=WorkflowState.DAG_VALIDATED,
            count=len(dag.tasks),
            timestamp=checked_request.requested_at,
        )
        sequence += 1
        waiting = _snapshot(
            state=WorkflowState.WAITING_APPROVAL,
            requirements=requirements,
            context=context,
            risks=risks,
            plan=plan,
            dag=dag,
            schedule=(),
            progress_sequence=sequence,
        )
        self._emit(
            sequence=sequence,
            workflow_id=checked_request.workflow_id,
            event=WorkflowProgressEventType.APPROVAL_REQUIRED,
            state=WorkflowState.WAITING_APPROVAL,
            count=len(dag.tasks),
            timestamp=checked_request.requested_at,
        )
        return waiting

    def schedule_workflow(
        self,
        snapshot: FrozenWorkflowSnapshot,
        approval: WorkflowApprovalContext,
    ) -> FrozenWorkflowSnapshot:
        try:
            checked_snapshot = _typed_copy(snapshot, FrozenWorkflowSnapshot)
            checked_approval = _typed_copy(approval, WorkflowApprovalContext)
        except (TypeError, ValueError, ValidationError):
            raise WorkflowApprovalRejected("workflow approval was rejected") from None
        validate_workflow_approval(checked_snapshot, checked_approval)
        sequence = checked_snapshot.progress_sequence + 1
        if checked_approval.decision is WorkflowApprovalDecision.DENIED:
            rejected = _snapshot(
                state=WorkflowState.REJECTED,
                requirements=checked_snapshot.requirements,
                context=checked_snapshot.context,
                risks=checked_snapshot.risks,
                plan=checked_snapshot.plan,
                dag=checked_snapshot.dag,
                schedule=(),
                progress_sequence=sequence,
            )
            self._emit(
                sequence=sequence,
                workflow_id=checked_snapshot.workflow_id,
                event=WorkflowProgressEventType.APPROVAL_REJECTED,
                state=WorkflowState.REJECTED,
                count=len(checked_snapshot.dag.tasks),
                timestamp=checked_approval.reviewed_at,
            )
            return rejected

        schedule = build_schedule(checked_snapshot.dag)
        scheduled = _snapshot(
            state=WorkflowState.SCHEDULED,
            requirements=checked_snapshot.requirements,
            context=checked_snapshot.context,
            risks=checked_snapshot.risks,
            plan=checked_snapshot.plan,
            dag=checked_snapshot.dag,
            schedule=schedule,
            progress_sequence=sequence,
        )
        self._emit(
            sequence=sequence,
            workflow_id=checked_snapshot.workflow_id,
            event=WorkflowProgressEventType.WORKFLOW_SCHEDULED,
            state=WorkflowState.SCHEDULED,
            count=len(schedule),
            timestamp=checked_approval.reviewed_at,
        )
        return scheduled


def _create_workflow_service(
    *,
    requirement_agent: RequirementAgentPort,
    planning_agent: EngineeringPlanningAgentPort,
    context_port: WorkflowContextPort,
    progress_sink: WorkflowProgressSink,
) -> EngineeringWorkflowPort:
    return _EngineeringWorkflowService(
        requirement_agent=requirement_agent,
        planning_agent=planning_agent,
        context_port=context_port,
        progress_sink=progress_sink,
    )
