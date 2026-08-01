from __future__ import annotations

import pytest

from embedded_copilot.hardware_intelligence import (
    HardwareContextProjection,
    HardwareMetadata,
    HardwareMetricUnit,
    HardwareObservation,
    hardware_context_fingerprint,
)
from embedded_copilot.optimization import (
    OptimizationAlgorithm,
    OptimizationConstraint,
    OptimizationMetricUnit,
    OptimizationRejected,
    OptimizationTarget,
    project_hardware_observation,
)

from .conftest import NOW


def _hardware_context() -> HardwareContextProjection:
    metadata = (HardwareMetadata(key="source", value="reference-1"),)
    return HardwareContextProjection(
        hardware_id="hardware-1",
        device_type="ESP32_S3",
        board_reference="board-1",
        safe_metadata=metadata,
        fingerprint=hardware_context_fingerprint(
            hardware_id="hardware-1",
            device_type="ESP32_S3",
            board_reference="board-1",
            safe_metadata=metadata,
        ),
    )


def _observations():
    return (
        HardwareObservation(
            sensor_id="current-1",
            metric_name="current",
            value=2.0,
            unit=HardwareMetricUnit.AMPERES,
            timestamp=NOW,
        ),
        HardwareObservation(
            sensor_id="temperature-1",
            metric_name="temperature",
            value=30.0,
            unit=HardwareMetricUnit.CELSIUS,
            timestamp=NOW,
        ),
        HardwareObservation(
            sensor_id="voltage-1",
            metric_name="voltage",
            value=5.0,
            unit=HardwareMetricUnit.VOLTS,
            timestamp=NOW,
        ),
    )


def _constraints():
    return (
        OptimizationConstraint(
            parameter="power_scale",
            current=1.0,
            minimum=0.9,
            maximum=1.0,
            unit=OptimizationMetricUnit.RATIO,
        ),
    )


def test_hardware_observations_project_to_immutable_request_with_derived_power() -> (
    None
):
    observations = _observations()
    context = _hardware_context()
    before_observations = tuple(item.model_dump_json() for item in observations)
    before_context = context.model_dump_json()
    request = project_hardware_observation(
        observations,
        optimization_id="optimization-1",
        hardware_context=context,
        constraints=_constraints(),
        optimization_target=OptimizationTarget.POWER,
        algorithm=OptimizationAlgorithm.POWER_MODEL,
        timestamp=NOW,
    )
    metrics = {item.name: item for item in request.baseline_metrics}
    assert metrics["power"].value == 10.0
    assert metrics["power"].unit is OptimizationMetricUnit.WATTS
    assert len(request.hardware_context.reference_ids) == 2
    assert tuple(item.model_dump_json() for item in observations) == before_observations
    assert context.model_dump_json() == before_context


def test_integration_rejects_untyped_missing_and_duplicate_observations() -> None:
    kwargs = dict(
        optimization_id="optimization-1",
        hardware_context=_hardware_context(),
        constraints=_constraints(),
        optimization_target=OptimizationTarget.POWER,
        algorithm=OptimizationAlgorithm.POWER_MODEL,
        timestamp=NOW,
    )
    with pytest.raises(OptimizationRejected):
        project_hardware_observation(list(_observations()), **kwargs)
    with pytest.raises(OptimizationRejected):
        project_hardware_observation(_observations()[1:], **kwargs)
    duplicate = _observations() + (_observations()[0],)
    with pytest.raises(OptimizationRejected):
        project_hardware_observation(duplicate, **kwargs)
