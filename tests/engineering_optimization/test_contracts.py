from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_optimization import (
    EngineeringOptimizationRequest,
    EngineeringOptimizationTarget,
    OptimizationDomain,
    create_engineering_optimization_runtime,
)
from tests.engineering_optimization.conftest import make_request, make_target


def test_factory_exposes_only_optimization_port() -> None:
    runtime = create_engineering_optimization_runtime()
    assert set(name for name in dir(runtime) if not name.startswith("_")) == {
        "engineering_optimization_port"
    }


def test_request_and_targets_are_frozen_strict_tuple_only_and_utc(
    optimization_sources,
) -> None:
    contract, execution, validation, feedback = optimization_sources
    target = make_target(contract)
    request = make_request(
        contract,
        (target,),
        execution=execution,
        validation=validation,
        feedback=feedback,
    )

    with pytest.raises(ValidationError):
        target.current_state = "CHANGED"
    with pytest.raises(ValidationError):
        EngineeringOptimizationTarget.model_validate(
            {**target.model_dump(mode="python"), "extra": "forbidden"}
        )
    with pytest.raises(ValidationError):
        EngineeringOptimizationRequest.model_validate(
            {**request.model_dump(mode="python"), "optimization_targets": [target]}
        )
    with pytest.raises(ValidationError):
        EngineeringOptimizationRequest.model_validate(
            {**request.model_dump(mode="python"), "requested_at": datetime(2026, 8, 10)}
        )


def test_target_sorting_binding_and_fingerprint_fail_closed(
    optimization_sources,
) -> None:
    contract, _, _, _ = optimization_sources
    first = make_target(contract, optimization_id="optimization-1")
    second = make_target(
        contract,
        optimization_id="optimization-2",
        domain=OptimizationDomain.RELIABILITY,
    )
    make_request(contract, (first, second))

    with pytest.raises(ValidationError):
        make_request(contract, (second, first))
    with pytest.raises(ValidationError):
        EngineeringOptimizationTarget.model_validate(
            {**first.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
    with pytest.raises(ValidationError):
        EngineeringOptimizationRequest.model_validate(
            {
                **make_request(contract, (first,)).model_dump(mode="python"),
                "fingerprint": "sha256:" + "0" * 64,
            }
        )
