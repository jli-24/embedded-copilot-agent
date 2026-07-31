"""Deterministic orchestration for the Agent Execution Runtime."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from embedded_copilot.agent_execution.contracts import (
    AgentCapabilityBinding,
    AgentExecutionBoundaryPort,
    AgentExecutionPort,
    AgentRegistryPort,
    ExecutionProgressSink,
    ExecutionVerificationPort,
)
from embedded_copilot.agent_execution.exceptions import (
    AgentExecutionRejected,
    ExecutionProgressUnavailable,
    ExecutionRecoveryRejected,
)
from embedded_copilot.agent_execution.models import (
    AgentBindingMetadata,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentExecutionResultStatus,
    AgentExecutionSnapshot,
    AgentExecutionState,
    AgentInvocationRequest,
    AgentResolutionRequest,
    ExecutionApprovalContext,
    ExecutionApprovalDecision,
    ExecutionFailureCode,
    ExecutionProgressEvent,
    ExecutionResultProjection,
    ExecutionVerificationRequest,
    ExecutionVerificationResult,
    ExecutionVerificationStatus,
    agent_execution_snapshot_fingerprint,
)

_ContractT = TypeVar("_ContractT", bound=BaseModel)


def _typed_copy(value: object, expected_type: type[_ContractT]) -> _ContractT:
    """Deep-copy a typed contract without a serialization round-trip."""
    if type(value) is not expected_type:
        raise AgentExecutionRejected("execution contract is invalid")
    try:
        copied = value.model_copy(deep=True)
        return expected_type.model_validate(copied)
    except (TypeError, ValueError, ValidationError):
        raise AgentExecutionRejected("execution contract is invalid") from None


class _AgentExecutionService(AgentExecutionPort):
    __slots__ = ("__agent_registry", "__progress_sink", "__verification_port")

    def __init__(
        self,
        *,
        agent_registry: AgentRegistryPort,
        progress_sink: ExecutionProgressSink,
        verification_port: ExecutionVerificationPort,
    ) -> None:
        self.__agent_registry = agent_registry
        self.__progress_sink = progress_sink
        self.__verification_port = verification_port

    def execute_task(self, request: AgentExecutionRequest) -> AgentExecutionSnapshot:
        safe_request = _typed_copy(request, AgentExecutionRequest)
        sequence = self._emit(
            request=safe_request,
            state=AgentExecutionState.CREATED,
            sequence=1,
            timestamp=safe_request.timestamp,
        )
        return self._execute_attempt(
            request=safe_request,
            attempt=1,
            sequence=sequence,
            timestamp=safe_request.timestamp,
        )

    def resume_execution(
        self,
        snapshot: AgentExecutionSnapshot,
        approval: ExecutionApprovalContext,
    ) -> AgentExecutionSnapshot:
        try:
            safe_snapshot = _typed_copy(snapshot, AgentExecutionSnapshot)
            safe_approval = _typed_copy(approval, ExecutionApprovalContext)
        except AgentExecutionRejected:
            raise ExecutionRecoveryRejected("execution recovery is rejected") from None
        self._validate_approval_binding(safe_snapshot, safe_approval)

        if (
            safe_snapshot.state
            in (AgentExecutionState.FAILED, AgentExecutionState.TIMEOUT)
            and safe_snapshot.attempt == 1
            and safe_approval.decision is ExecutionApprovalDecision.REQUESTED
        ):
            sequence = self._emit(
                request=safe_snapshot.request,
                state=AgentExecutionState.WAIT_HUMAN,
                sequence=safe_snapshot.progress_sequence + 1,
                timestamp=safe_approval.reviewed_at,
            )
            return self._snapshot(
                request=safe_snapshot.request,
                state=AgentExecutionState.WAIT_HUMAN,
                attempt=1,
                progress_sequence=sequence,
            )

        if safe_snapshot.state is not AgentExecutionState.WAIT_HUMAN:
            raise ExecutionRecoveryRejected("execution recovery is rejected")
        if safe_approval.decision is ExecutionApprovalDecision.DENIED:
            sequence = self._emit(
                request=safe_snapshot.request,
                state=AgentExecutionState.CANCELLED,
                sequence=safe_snapshot.progress_sequence + 1,
                timestamp=safe_approval.reviewed_at,
            )
            return self._snapshot(
                request=safe_snapshot.request,
                state=AgentExecutionState.CANCELLED,
                attempt=1,
                progress_sequence=sequence,
                failure_code=ExecutionFailureCode.APPROVAL_DENIED,
            )
        if safe_approval.decision is not ExecutionApprovalDecision.APPROVED:
            raise ExecutionRecoveryRejected("execution recovery is rejected")
        return self._execute_attempt(
            request=safe_snapshot.request,
            attempt=2,
            sequence=safe_snapshot.progress_sequence,
            timestamp=safe_approval.reviewed_at,
        )

    def _execute_attempt(
        self,
        *,
        request: AgentExecutionRequest,
        attempt: int,
        sequence: int,
        timestamp,
    ) -> AgentExecutionSnapshot:
        resolution = AgentResolutionRequest(
            execution_id=request.execution_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            agent_type=request.agent_type,
            attempt=attempt,
        )
        try:
            raw_binding = self.__agent_registry.resolve(resolution)
            binding = self._binding(raw_binding, request.agent_type)
        except Exception:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.AGENT_UNAVAILABLE,
                sequence=sequence,
                timestamp=timestamp,
            )

        sequence = self._emit(
            request=request,
            state=AgentExecutionState.READY,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        sequence = self._emit(
            request=request,
            state=AgentExecutionState.RUNNING,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        invocation = AgentInvocationRequest(request=request, attempt=attempt)
        try:
            raw_result = binding.execution_port.execute(invocation)
        except TimeoutError:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.TIMEOUT,
                attempt=attempt,
                failure_code=ExecutionFailureCode.AGENT_TIMEOUT,
                sequence=sequence,
                timestamp=timestamp,
            )
        except Exception:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.AGENT_UNAVAILABLE,
                sequence=sequence,
                timestamp=timestamp,
            )
        try:
            result = _typed_copy(raw_result, AgentExecutionResult)
            self._validate_result_binding(result, request)
        except (AgentExecutionRejected, ValueError):
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.AGENT_RESULT_REJECTED,
                sequence=sequence,
                timestamp=timestamp,
            )

        projection = ExecutionResultProjection(
            status=result.status,
            summary=result.summary,
            artifacts=result.artifacts,
            metrics=result.metrics,
            fingerprint=result.fingerprint,
        )
        sequence = self._emit(
            request=request,
            state=AgentExecutionState.VERIFYING,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        verification_request = ExecutionVerificationRequest(
            execution_id=request.execution_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            agent_type=request.agent_type,
            attempt=attempt,
            result=result,
            timestamp=timestamp,
        )
        try:
            raw_verification = self.__verification_port.verify(verification_request)
            verification = _typed_copy(raw_verification, ExecutionVerificationResult)
            if (
                verification.execution_id != request.execution_id
                or verification.result_fingerprint != result.fingerprint
            ):
                raise ValueError("verification binding mismatch")
        except Exception:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.VERIFICATION_UNAVAILABLE,
                sequence=sequence,
                timestamp=timestamp,
            )

        if verification.status is ExecutionVerificationStatus.INVALID:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.VERIFICATION_INVALID,
                sequence=sequence,
                timestamp=timestamp,
            )
        if result.status is AgentExecutionResultStatus.FAILED:
            return self._terminal_failure(
                request=request,
                state=AgentExecutionState.FAILED,
                attempt=attempt,
                failure_code=ExecutionFailureCode.AGENT_FAILED,
                sequence=sequence,
                timestamp=timestamp,
                result_projection=projection,
            )
        sequence = self._emit(
            request=request,
            state=AgentExecutionState.SUCCESS,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        return self._snapshot(
            request=request,
            state=AgentExecutionState.SUCCESS,
            attempt=attempt,
            progress_sequence=sequence,
            result_projection=projection,
        )

    def _binding(self, value: object, agent_type: str) -> AgentCapabilityBinding:
        if type(value) is not AgentCapabilityBinding:
            raise AgentExecutionRejected("agent binding is invalid")
        metadata = _typed_copy(value.metadata, AgentBindingMetadata)
        if (
            metadata.agent_type != agent_type
            or "EXECUTE_TASK" not in metadata.capabilities
            or not isinstance(value.execution_port, AgentExecutionBoundaryPort)
        ):
            raise AgentExecutionRejected("agent binding is invalid")
        return AgentCapabilityBinding(
            metadata=metadata,
            execution_port=value.execution_port,
        )

    @staticmethod
    def _validate_result_binding(
        result: AgentExecutionResult, request: AgentExecutionRequest
    ) -> None:
        if (
            result.execution_id != request.execution_id
            or result.workflow_id != request.workflow_id
            or result.task_id != request.task_id
            or result.agent_type != request.agent_type
        ):
            raise ValueError("result binding mismatch")

    @staticmethod
    def _validate_approval_binding(
        snapshot: AgentExecutionSnapshot,
        approval: ExecutionApprovalContext,
    ) -> None:
        if (
            approval.execution_id != snapshot.execution_id
            or approval.workflow_id != snapshot.workflow_id
            or approval.task_id != snapshot.task_id
            or approval.agent_type != snapshot.agent_type
            or approval.attempt != snapshot.attempt
            or approval.snapshot_fingerprint != snapshot.fingerprint
        ):
            raise ExecutionRecoveryRejected("execution recovery is rejected")

    def _terminal_failure(
        self,
        *,
        request: AgentExecutionRequest,
        state: AgentExecutionState,
        attempt: int,
        failure_code: ExecutionFailureCode,
        sequence: int,
        timestamp,
        result_projection: ExecutionResultProjection | None = None,
    ) -> AgentExecutionSnapshot:
        sequence = self._emit(
            request=request,
            state=state,
            sequence=sequence + 1,
            timestamp=timestamp,
        )
        return self._snapshot(
            request=request,
            state=state,
            attempt=attempt,
            progress_sequence=sequence,
            result_projection=result_projection,
            failure_code=failure_code,
        )

    def _emit(
        self,
        *,
        request: AgentExecutionRequest,
        state: AgentExecutionState,
        sequence: int,
        timestamp,
    ) -> int:
        event = ExecutionProgressEvent(
            sequence=sequence,
            execution_id=request.execution_id,
            workflow_id=request.workflow_id,
            state=state,
            timestamp=timestamp,
        )
        try:
            self.__progress_sink.emit(event)
        except Exception:
            raise ExecutionProgressUnavailable(
                "execution progress is unavailable"
            ) from None
        return sequence

    @staticmethod
    def _snapshot(
        *,
        request: AgentExecutionRequest,
        state: AgentExecutionState,
        attempt: int,
        progress_sequence: int,
        result_projection: ExecutionResultProjection | None = None,
        failure_code: ExecutionFailureCode | None = None,
    ) -> AgentExecutionSnapshot:
        values = {
            "execution_id": request.execution_id,
            "workflow_id": request.workflow_id,
            "task_id": request.task_id,
            "agent_type": request.agent_type,
            "request": request,
            "state": state,
            "attempt": attempt,
            "result_projection": result_projection,
            "failure_code": failure_code,
            "progress_sequence": progress_sequence,
        }
        return AgentExecutionSnapshot(
            **values,
            fingerprint=agent_execution_snapshot_fingerprint(**values),
        )


def _create_agent_execution_service(
    *,
    agent_registry: AgentRegistryPort,
    progress_sink: ExecutionProgressSink,
    verification_port: ExecutionVerificationPort,
) -> AgentExecutionPort:
    return _AgentExecutionService(
        agent_registry=agent_registry,
        progress_sink=progress_sink,
        verification_port=verification_port,
    )
