"""Deterministic, proposal-only Optimization Runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.optimization.approval.context import (
    OptimizationApprovalContext,
)
from embedded_copilot.optimization.contracts import (
    OptimizationEvaluationPort,
    OptimizationProgressSink,
    OptimizationRegistryPort,
)
from embedded_copilot.optimization.exceptions import (
    OptimizationProgressUnavailable,
    OptimizationRejected,
)
from embedded_copilot.optimization.models import (
    OptimizationAlgorithmMetadata,
    OptimizationApprovalDecision,
    OptimizationEvaluationProjection,
    OptimizationEvaluationRequest,
    OptimizationEvaluationStatus,
    OptimizationFailureCode,
    OptimizationInvocationRequest,
    OptimizationParameterRange,
    OptimizationPlan,
    OptimizationProgressEvent,
    OptimizationProgressEventType,
    OptimizationProposal,
    OptimizationRequest,
    OptimizationResolutionRequest,
    OptimizationSnapshot,
    OptimizationState,
    optimization_plan_fingerprint,
    optimization_request_fingerprint,
    optimization_snapshot_fingerprint,
)


@dataclass
class _ExecutionRecord:
    planned_fingerprint: str | None = None
    evaluated_fingerprint: str | None = None
    evaluation_started: bool = False
    consumed: bool = False


class _OptimizationService:
    def __init__(
        self,
        *,
        registry: OptimizationRegistryPort,
        evaluator: OptimizationEvaluationPort,
        progress_sink: OptimizationProgressSink,
    ) -> None:
        self._registry = registry
        self._evaluator = evaluator
        self._progress_sink = progress_sink
        self._records: dict[str, _ExecutionRecord] = {}

    def create_plan(self, request: OptimizationRequest) -> OptimizationSnapshot:
        try:
            request_copy = _typed_copy(request, OptimizationRequest)
        except Exception:
            raise OptimizationRejected("optimization rejected") from None
        identifier = request_copy.optimization_id
        if identifier in self._records:
            raise OptimizationRejected("optimization rejected") from None
        record = _ExecutionRecord()
        self._records[identifier] = record
        self._emit(
            request_copy,
            sequence=1,
            state=OptimizationState.CREATED,
            event=OptimizationProgressEventType.OPTIMIZATION_CREATED,
        )
        try:
            request_fingerprint = optimization_request_fingerprint(request_copy)
            resolution = OptimizationResolutionRequest(
                optimization_id=identifier,
                target=request_copy.target,
                algorithm=request_copy.algorithm,
                request_fingerprint=request_fingerprint,
            )
            optimizer = self._registry.resolve(resolution)
            metadata = _typed_copy(optimizer.metadata, OptimizationAlgorithmMetadata)
            self._validate_metadata(request_copy, metadata)
            parameter_space = self._parameter_space(request_copy, metadata)
            plan_values = dict(
                request=request_copy,
                request_fingerprint=request_fingerprint,
                algorithm_metadata=metadata,
                parameter_space=parameter_space,
                objective=metadata.objective,
            )
            plan = OptimizationPlan(
                **plan_values,
                fingerprint=optimization_plan_fingerprint(**plan_values),
            )
            proposal = _typed_copy(
                optimizer.propose(
                    OptimizationInvocationRequest(
                        plan=plan, timestamp=request_copy.timestamp
                    )
                ),
                OptimizationProposal,
            )
            self._validate_proposal(plan, proposal)
        except TimeoutError:
            return self._failure(
                request_copy,
                state=OptimizationState.TIMEOUT,
                code=OptimizationFailureCode.OPTIMIZER_TIMEOUT,
                sequence=2,
            )
        except Exception:
            return self._failure(
                request_copy,
                state=OptimizationState.FAILED,
                code=(
                    OptimizationFailureCode.REGISTRY_UNAVAILABLE
                    if "optimizer" not in locals()
                    else OptimizationFailureCode.OPTIMIZER_REJECTED
                ),
                sequence=2,
            )
        snapshot = self._snapshot(
            request=request_copy,
            plan=plan,
            proposal=proposal,
            state=OptimizationState.PLANNED,
            sequence=2,
        )
        record.planned_fingerprint = snapshot.fingerprint
        self._emit(
            request_copy,
            sequence=2,
            state=OptimizationState.PLANNED,
            event=OptimizationProgressEventType.OPTIMIZATION_PLANNED,
        )
        return snapshot

    def evaluate(self, snapshot: OptimizationSnapshot) -> OptimizationSnapshot:
        try:
            snapshot_copy = _typed_copy(snapshot, OptimizationSnapshot)
        except Exception:
            raise OptimizationRejected("optimization rejected") from None
        if (
            snapshot_copy.state is not OptimizationState.PLANNED
            or snapshot_copy.plan is None
            or snapshot_copy.proposal is None
        ):
            raise OptimizationRejected("optimization rejected") from None
        record = self._record_for(snapshot_copy)
        if record.evaluation_started:
            raise OptimizationRejected("optimization rejected") from None
        record.evaluation_started = True
        self._emit(
            snapshot_copy.request,
            sequence=3,
            state=OptimizationState.RUNNING,
            event=OptimizationProgressEventType.EVALUATION_RUNNING,
        )
        try:
            projection = _typed_copy(
                self._evaluator.evaluate(
                    OptimizationEvaluationRequest(
                        plan=snapshot_copy.plan,
                        proposal=snapshot_copy.proposal,
                        timestamp=snapshot_copy.request.timestamp,
                    )
                ),
                OptimizationEvaluationProjection,
            )
            self._validate_evaluation(snapshot_copy, projection)
        except TimeoutError:
            return self._failure_from_snapshot(
                snapshot_copy,
                state=OptimizationState.TIMEOUT,
                code=OptimizationFailureCode.EVALUATION_TIMEOUT,
                sequence=4,
            )
        except Exception as error:
            code = (
                OptimizationFailureCode.EVALUATOR_UNAVAILABLE
                if not isinstance(error, (TypeError, ValueError))
                else OptimizationFailureCode.EVALUATION_INVALID
            )
            return self._failure_from_snapshot(
                snapshot_copy,
                state=OptimizationState.FAILED,
                code=code,
                sequence=4,
            )
        if projection.validation_status is OptimizationEvaluationStatus.INVALID:
            return self._failure_from_snapshot(
                snapshot_copy,
                state=OptimizationState.FAILED,
                code=OptimizationFailureCode.EVALUATION_INVALID,
                sequence=4,
            )
        evaluated = self._snapshot(
            request=snapshot_copy.request,
            plan=snapshot_copy.plan,
            proposal=snapshot_copy.proposal,
            evaluation=projection,
            state=OptimizationState.EVALUATED,
            sequence=4,
        )
        record.evaluated_fingerprint = evaluated.fingerprint
        self._emit(
            snapshot_copy.request,
            sequence=4,
            state=OptimizationState.EVALUATED,
            event=OptimizationProgressEventType.OPTIMIZATION_EVALUATED,
        )
        return evaluated

    def approve(
        self,
        snapshot: OptimizationSnapshot,
        approval: OptimizationApprovalContext,
    ) -> OptimizationSnapshot:
        try:
            snapshot_copy = _typed_copy(snapshot, OptimizationSnapshot)
            approval_copy = _typed_copy(approval, OptimizationApprovalContext)
        except Exception:
            raise OptimizationRejected("optimization rejected") from None
        if (
            snapshot_copy.state is not OptimizationState.EVALUATED
            or snapshot_copy.proposal is None
            or snapshot_copy.evaluation is None
        ):
            raise OptimizationRejected("optimization rejected") from None
        record = self._record_for(snapshot_copy, evaluated=True)
        if record.consumed:
            raise OptimizationRejected("optimization rejected") from None
        self._validate_approval(snapshot_copy, approval_copy)
        record.consumed = True
        if approval_copy.decision is OptimizationApprovalDecision.REJECTED:
            terminal = self._snapshot(
                request=snapshot_copy.request,
                plan=snapshot_copy.plan,
                proposal=snapshot_copy.proposal,
                evaluation=snapshot_copy.evaluation,
                approval=approval_copy,
                state=OptimizationState.CANCELLED,
                failure_code=OptimizationFailureCode.APPROVAL_REJECTED,
                sequence=5,
            )
            self._emit(
                snapshot_copy.request,
                sequence=5,
                state=OptimizationState.CANCELLED,
                event=OptimizationProgressEventType.OPTIMIZATION_CANCELLED,
                timestamp=approval_copy.timestamp,
            )
            return terminal
        self._emit(
            snapshot_copy.request,
            sequence=5,
            state=OptimizationState.APPROVED,
            event=OptimizationProgressEventType.OPTIMIZATION_APPROVED,
            timestamp=approval_copy.timestamp,
        )
        terminal = self._snapshot(
            request=snapshot_copy.request,
            plan=snapshot_copy.plan,
            proposal=snapshot_copy.proposal,
            evaluation=snapshot_copy.evaluation,
            approval=approval_copy,
            state=OptimizationState.SUCCESS,
            sequence=6,
        )
        self._emit(
            snapshot_copy.request,
            sequence=6,
            state=OptimizationState.SUCCESS,
            event=OptimizationProgressEventType.OPTIMIZATION_SUCCEEDED,
            timestamp=approval_copy.timestamp,
        )
        return terminal

    def _record_for(
        self, snapshot: OptimizationSnapshot, *, evaluated: bool = False
    ) -> _ExecutionRecord:
        record = self._records.get(snapshot.request.optimization_id)
        expected = (
            record.evaluated_fingerprint
            if record is not None and evaluated
            else record.planned_fingerprint if record is not None else None
        )
        if record is None or expected != snapshot.fingerprint:
            raise OptimizationRejected("optimization rejected") from None
        return record

    @staticmethod
    def _validate_metadata(
        request: OptimizationRequest, metadata: OptimizationAlgorithmMetadata
    ) -> None:
        if (
            metadata.algorithm is not request.algorithm
            or metadata.target is not request.target
        ):
            raise ValueError("optimizer binding mismatch")

    @staticmethod
    def _parameter_space(
        request: OptimizationRequest, metadata: OptimizationAlgorithmMetadata
    ) -> tuple[OptimizationParameterRange, ...]:
        ranges = {item.parameter: item for item in metadata.parameter_space}
        for constraint in request.constraints:
            bound = ranges.get(constraint.parameter)
            if bound is None or bound.unit is not constraint.unit:
                raise ValueError("constraint binding mismatch")
            minimum = max(bound.minimum, constraint.minimum)
            maximum = min(bound.maximum, constraint.maximum)
            if minimum > maximum:
                raise ValueError("constraint intersection empty")
            ranges[constraint.parameter] = OptimizationParameterRange(
                parameter=bound.parameter,
                minimum=minimum,
                maximum=maximum,
                unit=bound.unit,
            )
        return tuple(sorted(ranges.values(), key=lambda item: item.parameter))

    @staticmethod
    def _validate_proposal(
        plan: OptimizationPlan, proposal: OptimizationProposal
    ) -> None:
        if (
            proposal.optimization_id != plan.request.optimization_id
            or proposal.plan_fingerprint != plan.fingerprint
        ):
            raise ValueError("proposal binding mismatch")
        ranges = {item.parameter: item for item in plan.parameter_space}
        for change in proposal.parameter_changes:
            bound = ranges.get(change.parameter)
            if (
                bound is None
                or bound.unit is not change.unit
                or not bound.minimum <= change.after <= bound.maximum
            ):
                raise ValueError("proposal range rejected")
        before = tuple((item.name, item.unit) for item in plan.request.baseline_metrics)
        after = tuple((item.name, item.unit) for item in proposal.metrics_projection)
        if before != after:
            raise ValueError("proposal metrics rejected")

    @staticmethod
    def _validate_evaluation(
        snapshot: OptimizationSnapshot,
        projection: OptimizationEvaluationProjection,
    ) -> None:
        if (
            projection.optimization_id != snapshot.request.optimization_id
            or projection.proposal_fingerprint != snapshot.proposal.fingerprint
            or projection.before_metrics != snapshot.request.baseline_metrics
            or projection.after_metrics != snapshot.proposal.metrics_projection
        ):
            raise ValueError("evaluation binding mismatch")

    @staticmethod
    def _validate_approval(
        snapshot: OptimizationSnapshot, approval: OptimizationApprovalContext
    ) -> None:
        if (
            approval.optimization_id != snapshot.request.optimization_id
            or approval.evaluated_snapshot_fingerprint != snapshot.fingerprint
            or approval.proposal_fingerprint != snapshot.proposal.fingerprint
            or approval.evaluation_fingerprint != snapshot.evaluation.fingerprint
        ):
            raise OptimizationRejected("optimization rejected") from None

    def _failure(
        self,
        request: OptimizationRequest,
        *,
        state: OptimizationState,
        code: OptimizationFailureCode,
        sequence: int,
    ) -> OptimizationSnapshot:
        terminal = self._snapshot(
            request=request,
            state=state,
            failure_code=code,
            sequence=sequence,
        )
        self._emit_failure(request, state=state, sequence=sequence)
        return terminal

    def _failure_from_snapshot(
        self,
        snapshot: OptimizationSnapshot,
        *,
        state: OptimizationState,
        code: OptimizationFailureCode,
        sequence: int,
    ) -> OptimizationSnapshot:
        terminal = self._snapshot(
            request=snapshot.request,
            plan=snapshot.plan,
            proposal=snapshot.proposal,
            state=state,
            failure_code=code,
            sequence=sequence,
        )
        self._emit_failure(snapshot.request, state=state, sequence=sequence)
        return terminal

    def _emit_failure(
        self, request: OptimizationRequest, *, state: OptimizationState, sequence: int
    ) -> None:
        event = (
            OptimizationProgressEventType.OPTIMIZATION_TIMED_OUT
            if state is OptimizationState.TIMEOUT
            else OptimizationProgressEventType.OPTIMIZATION_FAILED
        )
        self._emit(request, sequence=sequence, state=state, event=event)

    def _emit(
        self,
        request: OptimizationRequest,
        *,
        sequence: int,
        state: OptimizationState,
        event: OptimizationProgressEventType,
        timestamp=None,
    ) -> None:
        try:
            self._progress_sink.emit(
                OptimizationProgressEvent(
                    sequence=sequence,
                    optimization_id=request.optimization_id,
                    state=state,
                    event=event,
                    timestamp=timestamp or request.timestamp,
                )
            )
        except Exception:
            raise OptimizationProgressUnavailable(
                "optimization progress unavailable"
            ) from None

    @staticmethod
    def _snapshot(
        *,
        request: OptimizationRequest,
        state: OptimizationState,
        sequence: int,
        plan: OptimizationPlan | None = None,
        proposal: OptimizationProposal | None = None,
        evaluation: OptimizationEvaluationProjection | None = None,
        approval: OptimizationApprovalContext | None = None,
        failure_code: OptimizationFailureCode | None = None,
    ) -> OptimizationSnapshot:
        values = dict(
            request=request,
            plan=plan,
            proposal=proposal,
            evaluation=evaluation,
            approval=approval,
            state=state,
            failure_code=failure_code,
            progress_sequence=sequence,
        )
        return OptimizationSnapshot(
            **values,
            fingerprint=optimization_snapshot_fingerprint(**values),
        )


def _typed_copy(value, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed optimization contract required")
    return expected_type.model_validate(value.model_copy(deep=True))
