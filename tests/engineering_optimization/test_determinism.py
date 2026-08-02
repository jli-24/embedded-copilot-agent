from __future__ import annotations

from embedded_copilot.engineering_optimization import (
    canonical_optimization_json,
    create_engineering_optimization_runtime,
)
from tests.engineering_optimization.conftest import make_request, make_target


def test_optimization_analysis_is_deterministic_across_100_calls(
    optimization_sources,
) -> None:
    contract, execution, validation, feedback = optimization_sources
    request = make_request(
        contract,
        (make_target(contract),),
        execution=execution,
        validation=validation,
        feedback=feedback,
    )
    before = request.model_dump(mode="json")
    port = create_engineering_optimization_runtime().engineering_optimization_port()

    results = tuple(port.analyze(request) for _ in range(100))

    assert all(result == results[0] for result in results)
    assert len({result.fingerprint for result in results}) == 1
    assert len({hash(result) for result in results}) == 1
    assert len({canonical_optimization_json(result) for result in results}) == 1
    assert request.model_dump(mode="json") == before
