from __future__ import annotations

from embedded_copilot.engineering_artifacts import create_engineering_artifact_runtime


def test_generation_is_identical_across_one_hundred_calls(generation_request) -> None:
    port = create_engineering_artifact_runtime().engineering_artifact_port()
    before = generation_request.model_dump(mode="python")

    results = tuple(port.generate(generation_request) for _ in range(100))

    assert all(result == results[0] for result in results)
    assert len({result.fingerprint for result in results}) == 1
    assert len({hash(result) for result in results}) == 1
    assert len({result.model_dump_json() for result in results}) == 1
    assert generation_request.model_dump(mode="python") == before
