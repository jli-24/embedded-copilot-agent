from __future__ import annotations

from embedded_copilot.engineering_execution import create_engineering_execution_runtime
from tests.engineering_execution.conftest import make_request
from tests.engineering_execution.test_runtime import BuildPortFake


def test_contract_and_report_are_deterministic_across_one_hundred_calls(
    artifact_report,
) -> None:
    request = make_request(artifact_report)
    before = request.model_dump(mode="python")
    port = BuildPortFake()
    runtime_port = create_engineering_execution_runtime(
        build_port=port
    ).engineering_execution_port()
    reports = tuple(runtime_port.execute(request) for _ in range(100))
    assert all(report == reports[0] for report in reports)
    assert len({report.execution_contract.fingerprint for report in reports}) == 1
    assert len({report.approval_fingerprint for report in reports}) == 1
    assert len({report.fingerprint for report in reports}) == 1
    assert len({hash(report) for report in reports}) == 1
    assert len({report.model_dump_json() for report in reports}) == 1
    assert request.model_dump(mode="python") == before
    assert len(port.calls) == 100
