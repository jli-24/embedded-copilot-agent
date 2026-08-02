"""Execution orchestration with exact binding and single-use replay protection."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from embedded_copilot.execution_runtime.approval.context import (
    ExecutionApprovalContext,
)
from embedded_copilot.execution_runtime.contracts import (
    ExecutionExecutorPort,
    ExecutionExecutorRegistryPort,
    ExecutionPort,
    ExecutionProgressSink,
    ExecutionVerificationPort,
)
from embedded_copilot.execution_runtime.exceptions import (
    ExecutionProgressUnavailable,
    ExecutionRejected,
    ExecutionTimeout,
)
from embedded_copilot.execution_runtime.models import (
    ExecutionExecutorMetadata,
    ExecutionExecutorResolutionRequest,
    ExecutionFailureCode,
    ExecutionInvocationRequest,
    ExecutionPlan,
    ExecutionPreparationRequest,
    ExecutionProgressEvent,
    ExecutionProgressEventType,
    ExecutionResultProjection,
    ExecutionResultStatus,
    ExecutionSnapshot,
    ExecutionState,
    ExecutionVerificationProjection,
    ExecutionVerificationRequest,
    ExecutionVerificationStatus,
    execution_plan_fingerprint,
    execution_snapshot_fingerprint,
)
from embedded_copilot.execution_runtime.registry.registry import (
    _ExecutionExecutorBinding,
)
from embedded_copilot.execution_runtime.verification.projection import copy_exact


@dataclass(slots=True)
class _PreparedExecution:
    ready_fingerprint: str
    binding: _ExecutionExecutorBinding
    consumed: bool = False


_EVENTS = {
    ExecutionState.CREATED: ExecutionProgressEventType.EXECUTION_CREATED,
    ExecutionState.READY: ExecutionProgressEventType.EXECUTION_READY,
    ExecutionState.APPROVED: ExecutionProgressEventType.EXECUTION_APPROVED,
    ExecutionState.RUNNING: ExecutionProgressEventType.EXECUTION_RUNNING,
    ExecutionState.VERIFYING: ExecutionProgressEventType.EXECUTION_VERIFYING,
    ExecutionState.SUCCESS: ExecutionProgressEventType.EXECUTION_SUCCEEDED,
    ExecutionState.FAILED: ExecutionProgressEventType.EXECUTION_FAILED,
    ExecutionState.TIMEOUT: ExecutionProgressEventType.EXECUTION_TIMED_OUT,
    ExecutionState.CANCELLED: ExecutionProgressEventType.EXECUTION_CANCELLED,
}


class _ExecutionService(ExecutionPort):
    def __init__(
        self,
        *,
        executor_registry: ExecutionExecutorRegistryPort,
        verification_port: ExecutionVerificationPort,
        progress_sink: ExecutionProgressSink,
    ) -> None:
        self._executor_registry = executor_registry
        self._verification_port = verification_port
        self._progress_sink = progress_sink
        self._lock = Lock()
        self._execution_ids: set[str] = set()
        self._prepared: dict[str, _PreparedExecution] = {}

    def prepare_execution(
        self, request: ExecutionPreparationRequest
    ) -> ExecutionSnapshot:
        safe_request = copy_exact(request, ExecutionPreparationRequest)
        with self._lock:
            if safe_request.execution_id in self._execution_ids:
                raise ExecutionRejected("execution request was rejected")
            self._execution_ids.add(safe_request.execution_id)

        plan = self._plan(safe_request)
        self._emit(plan, state=ExecutionState.CREATED, sequence=1)
        try:
            executor = self._executor_registry.resolve(
                ExecutionExecutorResolutionRequest(
                    execution_id=plan.execution_id,
                    executor_type=plan.executor_type,
                )
            )
        except Exception:
            return self._prepare_failure(
                plan, ExecutionFailureCode.EXECUTOR_UNAVAILABLE
            )

        if executor is None:
            return self._prepare_failure(
                plan, ExecutionFailureCode.EXECUTOR_UNAVAILABLE
            )

        binding = self._bind_executor(executor, plan)
        if binding is None:
            return self._prepare_failure(plan, ExecutionFailureCode.EXECUTOR_REJECTED)

        ready = self._snapshot(plan=plan, state=ExecutionState.READY, sequence=2)
        self._emit(plan, state=ExecutionState.READY, sequence=2)
        with self._lock:
            self._prepared[plan.execution_id] = _PreparedExecution(
                ready_fingerprint=ready.fingerprint,
                binding=binding,
            )
        return ready

    def execute(
        self,
        snapshot: ExecutionSnapshot,
        approval: ExecutionApprovalContext,
    ) -> ExecutionSnapshot:
        safe_snapshot = copy_exact(snapshot, ExecutionSnapshot)
        safe_approval = copy_exact(approval, ExecutionApprovalContext)
        decision = self._validate_approval(safe_snapshot, safe_approval)

        with self._lock:
            prepared = self._prepared.get(safe_snapshot.plan.execution_id)
            if (
                prepared is None
                or prepared.consumed
                or prepared.ready_fingerprint != safe_snapshot.fingerprint
            ):
                raise ExecutionRejected("execution request was rejected")
            prepared.consumed = True

        if decision == "approval_denied":
            return self._cancel(
                safe_snapshot,
                safe_approval,
                ExecutionFailureCode.APPROVAL_DENIED,
            )
        if decision == "revision_required":
            return self._cancel(
                safe_snapshot,
                safe_approval,
                ExecutionFailureCode.REVISION_REQUIRED,
            )

        plan = safe_snapshot.plan
        self._emit(
            plan,
            state=ExecutionState.APPROVED,
            sequence=3,
            timestamp=safe_approval.approval_timestamp,
        )
        self._emit(
            plan,
            state=ExecutionState.RUNNING,
            sequence=4,
            timestamp=safe_approval.approval_timestamp,
        )
        invocation = ExecutionInvocationRequest(
            plan=plan,
            approval_fingerprint=safe_approval.fingerprint,
        )
        try:
            raw_result = prepared.binding.executor.execute(invocation)
        except (TimeoutError, ExecutionTimeout):
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.TIMEOUT,
                failure=ExecutionFailureCode.EXECUTOR_TIMEOUT,
                sequence=5,
            )
        except Exception:
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.EXECUTOR_FAILED,
                sequence=5,
            )

        try:
            result = copy_exact(raw_result, ExecutionResultProjection)
        except ExecutionRejected:
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.EXECUTOR_REJECTED,
                sequence=5,
            )

        self._emit(
            plan,
            state=ExecutionState.VERIFYING,
            sequence=5,
            timestamp=safe_approval.approval_timestamp,
        )
        verification_request = ExecutionVerificationRequest(
            plan=plan,
            result=result,
            timestamp=safe_approval.approval_timestamp,
        )
        try:
            raw_verification = self._verification_port.verify(verification_request)
            verification = copy_exact(raw_verification, ExecutionVerificationProjection)
        except Exception:
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.VERIFICATION_UNAVAILABLE,
                sequence=6,
                result=result,
            )

        if (
            verification.execution_id != plan.execution_id
            or verification.result_fingerprint != result.fingerprint
        ):
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.VERIFICATION_INVALID,
                sequence=6,
                result=result,
            )
        if verification.status is ExecutionVerificationStatus.INVALID:
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.VERIFICATION_INVALID,
                sequence=6,
                result=result,
                verification=verification,
            )
        if result.status is ExecutionResultStatus.FAILED:
            return self._terminal_failure(
                plan,
                safe_approval,
                state=ExecutionState.FAILED,
                failure=ExecutionFailureCode.EXECUTOR_FAILED,
                sequence=6,
                result=result,
                verification=verification,
            )

        terminal = self._snapshot(
            plan=plan,
            state=ExecutionState.SUCCESS,
            sequence=6,
            approval_fingerprint=safe_approval.fingerprint,
            result=result,
            verification=verification,
        )
        self._emit(
            plan,
            state=ExecutionState.SUCCESS,
            sequence=6,
            timestamp=safe_approval.approval_timestamp,
        )
        return terminal

    @staticmethod
    def _plan(request: ExecutionPreparationRequest) -> ExecutionPlan:
        return ExecutionPlan(
            execution_id=request.execution_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            agent_type=request.agent_type,
            executor_type=request.executor_type,
            context=request.context.model_copy(deep=True),
            proposal=request.proposal.model_copy(deep=True),
            prepared_at=request.timestamp,
            fingerprint=execution_plan_fingerprint(
                execution_id=request.execution_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                agent_type=request.agent_type,
                executor_type=request.executor_type,
                context=request.context,
                proposal=request.proposal,
                prepared_at=request.timestamp,
            ),
        )

    @staticmethod
    def _bind_executor(
        executor: object, plan: ExecutionPlan
    ) -> _ExecutionExecutorBinding | None:
        if not isinstance(executor, ExecutionExecutorPort):
            return None
        try:
            metadata = copy_exact(executor.metadata, ExecutionExecutorMetadata)
        except Exception:
            return None
        if (
            metadata.executor_type is not plan.executor_type
            or "EXECUTE" not in metadata.capabilities
        ):
            return None
        return _ExecutionExecutorBinding(metadata=metadata, executor=executor)

    @staticmethod
    def _validate_approval(
        snapshot: ExecutionSnapshot, approval: ExecutionApprovalContext
    ) -> str:
        if (
            snapshot.state is not ExecutionState.READY
            or approval.execution_id != snapshot.plan.execution_id
            or approval.ready_snapshot_fingerprint != snapshot.fingerprint
            or approval.human_review.proposal_id != snapshot.plan.proposal.proposal_id
            or approval.human_review.proposal.fingerprint
            != snapshot.plan.proposal.proposal_fingerprint
            or approval.human_review.review.reviewer != approval.reviewer
            or approval.human_review.review.timestamp != approval.approval_timestamp
        ):
            raise ExecutionRejected("execution request was rejected")

        review = approval.human_review
        decision = review.review.decision.value
        state = review.state.value
        if decision == "APPROVED" and state == "COMPLETED":
            return "approved"
        if decision == "REJECTED" and state == "REJECTED":
            return "approval_denied"
        if decision == "CHANGES_REQUESTED" and state == "REVISION_REQUIRED":
            return "revision_required"
        raise ExecutionRejected("execution request was rejected")

    def _prepare_failure(
        self, plan: ExecutionPlan, failure: ExecutionFailureCode
    ) -> ExecutionSnapshot:
        failed = self._snapshot(
            plan=plan,
            state=ExecutionState.FAILED,
            sequence=2,
            failure=failure,
        )
        self._emit(plan, state=ExecutionState.FAILED, sequence=2)
        return failed

    def _cancel(
        self,
        snapshot: ExecutionSnapshot,
        approval: ExecutionApprovalContext,
        failure: ExecutionFailureCode,
    ) -> ExecutionSnapshot:
        cancelled = self._snapshot(
            plan=snapshot.plan,
            state=ExecutionState.CANCELLED,
            sequence=3,
            approval_fingerprint=approval.fingerprint,
            failure=failure,
        )
        self._emit(
            snapshot.plan,
            state=ExecutionState.CANCELLED,
            sequence=3,
            timestamp=approval.approval_timestamp,
        )
        return cancelled

    def _terminal_failure(
        self,
        plan: ExecutionPlan,
        approval: ExecutionApprovalContext,
        *,
        state: ExecutionState,
        failure: ExecutionFailureCode,
        sequence: int,
        result: ExecutionResultProjection | None = None,
        verification: ExecutionVerificationProjection | None = None,
    ) -> ExecutionSnapshot:
        terminal = self._snapshot(
            plan=plan,
            state=state,
            sequence=sequence,
            approval_fingerprint=approval.fingerprint,
            result=result,
            verification=verification,
            failure=failure,
        )
        self._emit(
            plan,
            state=state,
            sequence=sequence,
            timestamp=approval.approval_timestamp,
        )
        return terminal

    @staticmethod
    def _snapshot(
        *,
        plan: ExecutionPlan,
        state: ExecutionState,
        sequence: int,
        approval_fingerprint: str | None = None,
        result: ExecutionResultProjection | None = None,
        verification: ExecutionVerificationProjection | None = None,
        failure: ExecutionFailureCode | None = None,
    ) -> ExecutionSnapshot:
        fingerprint = execution_snapshot_fingerprint(
            plan=plan,
            state=state,
            approval_fingerprint=approval_fingerprint,
            result=result,
            verification=verification,
            failure_code=failure,
            progress_sequence=sequence,
        )
        return ExecutionSnapshot(
            plan=plan,
            state=state,
            approval_fingerprint=approval_fingerprint,
            result=result,
            verification=verification,
            failure_code=failure,
            progress_sequence=sequence,
            fingerprint=fingerprint,
        )

    def _emit(
        self,
        plan: ExecutionPlan,
        *,
        state: ExecutionState,
        sequence: int,
        timestamp=None,
    ) -> None:
        event = ExecutionProgressEvent(
            sequence=sequence,
            execution_id=plan.execution_id,
            workflow_id=plan.workflow_id,
            event=_EVENTS[state],
            state=state,
            timestamp=timestamp or plan.prepared_at,
        )
        try:
            self._progress_sink.emit(event)
        except Exception:
            raise ExecutionProgressUnavailable(
                "execution progress unavailable"
            ) from None


__all__: tuple[str, ...] = ()
