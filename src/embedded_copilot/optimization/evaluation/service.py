"""Pure before/after metric evaluation without a total score."""

from embedded_copilot.optimization.models import (
    OptimizationEvaluationProjection,
    OptimizationEvaluationRequest,
    OptimizationEvaluationStatus,
    OptimizationImprovement,
    optimization_evaluation_fingerprint,
)


class _DeterministicEvaluator:
    def evaluate(
        self, request: OptimizationEvaluationRequest
    ) -> OptimizationEvaluationProjection:
        before = request.plan.request.baseline_metrics
        after = request.proposal.metrics_projection
        before_keys = tuple((item.name, item.unit) for item in before)
        after_keys = tuple((item.name, item.unit) for item in after)
        status = (
            OptimizationEvaluationStatus.VALID
            if before_keys == after_keys
            else OptimizationEvaluationStatus.INVALID
        )
        after_map = {(item.name, item.unit): item for item in after}
        improvements = []
        if status is OptimizationEvaluationStatus.VALID:
            for item in before:
                projected = after_map[(item.name, item.unit)]
                delta = float(projected.value - item.value)
                percent = (
                    None if item.value == 0 else float(delta / abs(item.value) * 100.0)
                )
                improvements.append(
                    OptimizationImprovement(
                        metric_name=item.name,
                        unit=item.unit,
                        before=item.value,
                        after=projected.value,
                        delta=delta,
                        percent_change=percent,
                    )
                )
        values = dict(
            optimization_id=request.plan.request.optimization_id,
            proposal_fingerprint=request.proposal.fingerprint,
            before_metrics=before,
            after_metrics=after,
            improvement=tuple(improvements),
            validation_status=status,
        )
        return OptimizationEvaluationProjection(
            **values,
            fingerprint=optimization_evaluation_fingerprint(**values),
        )


def create_deterministic_evaluator() -> _DeterministicEvaluator:
    return _DeterministicEvaluator()
