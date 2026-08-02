"""Deterministic fakes and fixtures for Execution Runtime tests."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Barrier
from typing import Callable

import pytest

from embedded_copilot.execution_runtime import (
    ExecutionArtifactReference,
    ExecutionExecutorMetadata,
    ExecutionExecutorResolutionRequest,
    ExecutorType,
    ExecutionMetric,
    ExecutionMetricUnit,
    ExecutionPreparationRequest,
    ExecutionProgressEvent,
    ExecutionProposalReference,
    ExecutionResultProjection,
    ExecutionResultStatus,
    ExecutionVerificationProjection,
    ExecutionVerificationRequest,
    ExecutionVerificationStatus,
    execution_executor_metadata_fingerprint,
    execution_result_fingerprint,
    execution_verification_fingerprint,
)
from embedded_copilot.engineering_generation import ArtifactType
from embedded_copilot.human_loop import proposal_projection_fingerprint

NOW = datetime(2026, 7, 1, 9, 30, tzinfo=UTC)


class FakeExecutor:
    def __init__(
        self,
        executor_type: ExecutorType = ExecutorType.BUILD,
        *,
        behavior: Callable | None = None,
        barrier: Barrier | None = None,
    ) -> None:
        capabilities = ("EXECUTE",)
        self._metadata = ExecutionExecutorMetadata(
            binding_id="build-primary",
            executor_type=executor_type,
            capabilities=capabilities,
            fingerprint=execution_executor_metadata_fingerprint(
                binding_id="build-primary",
                executor_type=executor_type,
                capabilities=capabilities,
            ),
        )
        self.behavior = behavior
        self.barrier = barrier
        self.calls = []

    @property
    def metadata(self) -> ExecutionExecutorMetadata:
        return self._metadata

    def execute(self, request):
        self.calls.append(request)
        if self.barrier is not None:
            self.barrier.wait(timeout=2)
        if self.behavior is not None:
            return self.behavior(request)
        artifacts = (
            ExecutionArtifactReference(
                reference_id="artifact-build-1",
                artifact_type="BUILD_REPORT",
                status="READY",
            ),
        )
        metrics = (
            ExecutionMetric(
                name="warnings_count",
                value=0,
                unit=ExecutionMetricUnit.COUNT,
            ),
        )
        return ExecutionResultProjection(
            status=ExecutionResultStatus.SUCCESS,
            summary="Controlled build adapter completed.",
            artifacts=artifacts,
            metrics=metrics,
            fingerprint=execution_result_fingerprint(
                status=ExecutionResultStatus.SUCCESS,
                summary="Controlled build adapter completed.",
                artifacts=artifacts,
                metrics=metrics,
            ),
        )


class FakeRegistry:
    def __init__(self, executor=None, *, error: Exception | None = None) -> None:
        self.executor = executor
        self.error = error
        self.calls: list[ExecutionExecutorResolutionRequest] = []

    def resolve(self, request: ExecutionExecutorResolutionRequest):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.executor


class FakeVerifier:
    def __init__(
        self,
        status: ExecutionVerificationStatus = ExecutionVerificationStatus.VALID,
        *,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.error = error
        self.calls: list[ExecutionVerificationRequest] = []

    def verify(
        self, request: ExecutionVerificationRequest
    ) -> ExecutionVerificationProjection:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return ExecutionVerificationProjection(
            execution_id=request.plan.execution_id,
            result_fingerprint=request.result.fingerprint,
            status=self.status,
            fingerprint=execution_verification_fingerprint(
                execution_id=request.plan.execution_id,
                result_fingerprint=request.result.fingerprint,
                status=self.status,
            ),
        )


class RecordingProgressSink:
    def __init__(self, *, fail_on_sequence: int | None = None) -> None:
        self.fail_on_sequence = fail_on_sequence
        self.events: list[ExecutionProgressEvent] = []

    def emit(self, event: ExecutionProgressEvent) -> None:
        if event.sequence == self.fail_on_sequence:
            raise RuntimeError("sensitive progress backend path C:\\private")
        self.events.append(event)


@pytest.fixture
def preparation_request() -> ExecutionPreparationRequest:
    from embedded_copilot.execution_runtime import (
        ExecutionContextProjection,
        execution_context_fingerprint,
    )

    references = ("artifact-input-1", "context-safe-1")
    context = ExecutionContextProjection(
        context_id="agent-execution-1",
        summary="Verified agent result prepared for controlled execution.",
        reference_ids=references,
        fingerprint=execution_context_fingerprint(
            context_id="agent-execution-1",
            summary="Verified agent result prepared for controlled execution.",
            reference_ids=references,
        ),
    )
    proposal_fingerprint = proposal_projection_fingerprint(
        proposal_id="proposal-1",
        artifact_type=ArtifactType.FIRMWARE,
        artifact_version=1,
        summary="Reviewed execution proposal.",
        reference_ids=("artifact-input-1",),
    )
    return ExecutionPreparationRequest(
        execution_id="controlled-execution-1",
        workflow_id="workflow-1",
        task_id="task-1",
        agent_type="FIRMWARE_AGENT",
        executor_type=ExecutorType.BUILD,
        context=context,
        proposal=ExecutionProposalReference(
            proposal_id="proposal-1",
            proposal_fingerprint=proposal_fingerprint,
        ),
        timestamp=NOW,
    )
