from __future__ import annotations

from embedded_copilot.engineering_validation import create_hardware_validation_runtime


def test_validation_report_is_identical_across_one_hundred_calls(
    validation_setup,
) -> None:
    request, evidence_port = validation_setup
    port = create_hardware_validation_runtime(
        evidence_port=evidence_port
    ).hardware_validation_port()
    before = request.model_dump(mode="python")

    results = tuple(port.validate(request) for _ in range(100))

    assert all(result == results[0] for result in results)
    assert len({result.fingerprint for result in results}) == 1
    assert len({hash(result) for result in results}) == 1
    assert len({result.model_dump_json() for result in results}) == 1
    assert request.model_dump(mode="python") == before
    assert len(evidence_port.calls) == 100
