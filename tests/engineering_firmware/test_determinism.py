from __future__ import annotations

from embedded_copilot.engineering_firmware import create_engineering_firmware_runtime


def test_proposal_is_identical_across_one_hundred_calls(firmware_request) -> None:
    port = create_engineering_firmware_runtime().firmware_engineering_port()
    before = firmware_request.model_dump(mode="python")

    results = tuple(
        port.prepare_firmware_proposal(firmware_request) for _ in range(100)
    )

    assert all(result == results[0] for result in results)
    assert len({result.fingerprint for result in results}) == 1
    assert len({hash(result) for result in results}) == 1
    canonical = results[0].model_dump_json()
    assert all(result.model_dump_json() == canonical for result in results)
    assert firmware_request.model_dump(mode="python") == before
