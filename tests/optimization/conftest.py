from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.optimization import (
    OptimizationAlgorithm,
    OptimizationApprovalContext,
    OptimizationApprovalDecision,
    OptimizationConstraint,
    OptimizationContextProjection,
    OptimizationMetric,
    OptimizationMetricUnit,
    OptimizationRequest,
    OptimizationTarget,
    optimization_approval_fingerprint,
    optimization_context_fingerprint,
)

NOW = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)


def make_context() -> OptimizationContextProjection:
    references = ("sha256:" + "a" * 64, "sha256:" + "b" * 64)
    return OptimizationContextProjection(
        context_id="hardware-1",
        summary="Safe hardware observation projection.",
        reference_ids=references,
        fingerprint=optimization_context_fingerprint(
            context_id="hardware-1",
            summary="Safe hardware observation projection.",
            reference_ids=references,
        ),
    )


def make_request(
    target: OptimizationTarget = OptimizationTarget.POWER,
    algorithm: OptimizationAlgorithm = OptimizationAlgorithm.POWER_MODEL,
) -> OptimizationRequest:
    if algorithm is OptimizationAlgorithm.PID:
        metrics = (
            OptimizationMetric(
                name="error", value=1.0, unit=OptimizationMetricUnit.RATIO
            ),
            OptimizationMetric(
                name="previous_output",
                value=2.0,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
        constraints = (
            OptimizationConstraint(
                parameter="controller_output",
                current=2.0,
                minimum=-10.0,
                maximum=10.0,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
    elif algorithm is OptimizationAlgorithm.PERFORMANCE_MODEL:
        metrics = (
            OptimizationMetric(
                name="cpu_usage", value=40.0, unit=OptimizationMetricUnit.PERCENT
            ),
            OptimizationMetric(
                name="latency",
                value=100.0,
                unit=OptimizationMetricUnit.MILLISECONDS,
            ),
            OptimizationMetric(
                name="memory_usage",
                value=50.0,
                unit=OptimizationMetricUnit.PERCENT,
            ),
            OptimizationMetric(
                name="throughput", value=100.0, unit=OptimizationMetricUnit.HERTZ
            ),
        )
        constraints = (
            OptimizationConstraint(
                parameter="performance_scale",
                current=1.0,
                minimum=1.0,
                maximum=1.1,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
    else:
        metrics = (
            OptimizationMetric(
                name="current", value=2.0, unit=OptimizationMetricUnit.AMPERES
            ),
            OptimizationMetric(
                name="power", value=10.0, unit=OptimizationMetricUnit.WATTS
            ),
            OptimizationMetric(
                name="temperature",
                value=30.0,
                unit=OptimizationMetricUnit.CELSIUS,
            ),
            OptimizationMetric(
                name="voltage", value=5.0, unit=OptimizationMetricUnit.VOLTS
            ),
        )
        constraints = (
            OptimizationConstraint(
                parameter="power_scale",
                current=1.0,
                minimum=0.9,
                maximum=1.0,
                unit=OptimizationMetricUnit.RATIO,
            ),
        )
    return OptimizationRequest(
        optimization_id="optimization-1",
        hardware_context=make_context(),
        target=target,
        algorithm=algorithm,
        baseline_metrics=metrics,
        constraints=constraints,
        timestamp=NOW,
    )


class StaticRegistry:
    def __init__(self, algorithm_port: object) -> None:
        self.algorithm_port = algorithm_port
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        return self.algorithm_port


class RecordingProgressSink:
    def __init__(self, fail_on_sequence: int | None = None) -> None:
        self.events = []
        self.fail_on_sequence = fail_on_sequence

    def emit(self, event) -> None:
        if event.sequence == self.fail_on_sequence:
            raise RuntimeError("private progress sink")
        self.events.append(event)


def make_approval(snapshot, decision=OptimizationApprovalDecision.APPROVED):
    fingerprint = optimization_approval_fingerprint(
        optimization_id=snapshot.request.optimization_id,
        evaluated_snapshot_fingerprint=snapshot.fingerprint,
        proposal_fingerprint=snapshot.proposal.fingerprint,
        evaluation_fingerprint=snapshot.evaluation.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        timestamp=NOW,
    )
    return OptimizationApprovalContext(
        optimization_id=snapshot.request.optimization_id,
        evaluated_snapshot_fingerprint=snapshot.fingerprint,
        proposal_fingerprint=snapshot.proposal.fingerprint,
        evaluation_fingerprint=snapshot.evaluation.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        timestamp=NOW,
        fingerprint=fingerprint,
    )


@pytest.fixture
def power_request() -> OptimizationRequest:
    return make_request()
