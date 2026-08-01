"""Contract tests for the Execution Integration Runtime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.execution_runtime import (
    ExecutionArtifactReference,
    ExecutionContextProjection,
    ExecutionMetric,
    ExecutionMetricUnit,
    ExecutionPreparationRequest,
    ExecutionResultProjection,
    ExecutionResultStatus,
    execution_context_fingerprint,
    execution_result_fingerprint,
)


def test_contracts_are_frozen_strict_and_extra_forbidden(preparation_request) -> None:
    with pytest.raises(ValidationError):
        preparation_request.execution_id = "changed"
    with pytest.raises(ValidationError):
        ExecutionPreparationRequest.model_validate(
            {**preparation_request.model_dump(mode="python"), "provider": "unsafe"}
        )
    with pytest.raises(ValidationError):
        ExecutionContextProjection(
            context_id="context-1",
            summary="Safe summary.",
            reference_ids=["ref-1"],
            fingerprint="sha256:" + "0" * 64,
        )


def test_timestamp_is_timezone_aware_and_normalized(preparation_request) -> None:
    shifted = preparation_request.model_copy(
        update={
            "timestamp": datetime(
                2026, 7, 1, 17, 30, tzinfo=timezone(timedelta(hours=8))
            )
        }
    )
    validated = ExecutionPreparationRequest.model_validate(shifted)
    assert validated.timestamp == datetime(2026, 7, 1, 9, 30, tzinfo=UTC)
    with pytest.raises(ValidationError):
        ExecutionPreparationRequest.model_validate(
            preparation_request.model_copy(
                update={"timestamp": datetime(2026, 7, 1, 9, 30)}
            )
        )


def test_context_fingerprint_is_stable_and_rejects_tampering() -> None:
    references = ("a-ref", "b-ref")
    fingerprint = execution_context_fingerprint(
        context_id="context-1", summary="Safe summary.", reference_ids=references
    )
    first = ExecutionContextProjection(
        context_id="context-1",
        summary="Safe summary.",
        reference_ids=references,
        fingerprint=fingerprint,
    )
    second = ExecutionContextProjection.model_validate(first.model_copy(deep=True))
    assert first.fingerprint == second.fingerprint
    with pytest.raises(ValidationError):
        ExecutionContextProjection.model_validate(
            first.model_copy(update={"summary": "Tampered summary."})
        )


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_metrics_reject_non_finite_or_boolean_values(value) -> None:
    with pytest.raises(ValidationError):
        ExecutionMetric(name="duration_ms", value=value, unit="milliseconds")


def test_result_collections_are_sorted_unique_and_content_free() -> None:
    artifacts = (
        ExecutionArtifactReference(
            reference_id="artifact-1", artifact_type="BUILD_REPORT", status="READY"
        ),
    )
    metrics = (
        ExecutionMetric(
            name="duration_ms", value=12.5, unit=ExecutionMetricUnit.MILLISECONDS
        ),
    )
    result = ExecutionResultProjection(
        status=ExecutionResultStatus.SUCCESS,
        summary="Controlled adapter completed.",
        artifacts=artifacts,
        metrics=metrics,
        fingerprint=execution_result_fingerprint(
            status=ExecutionResultStatus.SUCCESS,
            summary="Controlled adapter completed.",
            artifacts=artifacts,
            metrics=metrics,
        ),
    )
    serialized = result.model_dump_json()
    assert "path" not in serialized.lower()
    assert "content" not in serialized.lower()
    assert "stdout" not in serialized.lower()
    with pytest.raises(ValidationError):
        ExecutionResultProjection.model_validate(
            result.model_copy(update={"artifacts": artifacts + artifacts})
        )
