from __future__ import annotations

from embedded_copilot.engineering_feedback import create_engineering_feedback_runtime
from tests.engineering_feedback.conftest import artifact_fingerprint, make_change_item
from tests.engineering_feedback.test_contracts import make_request


def test_feedback_report_is_deterministic_across_one_hundred_calls(
    feedback_sources,
) -> None:
    contract, execution, validation = feedback_sources
    item = make_change_item(artifact_fingerprint(contract))
    request = make_request(
        contract,
        (item,),
        execution=execution,
        validation=validation,
    )
    before = request.model_dump(mode="json")
    port = create_engineering_feedback_runtime().engineering_feedback_port()

    reports = tuple(port.submit_feedback(request) for _ in range(100))

    assert all(report == reports[0] for report in reports)
    assert len({report.fingerprint for report in reports}) == 1
    assert len({report.change_requests[0].fingerprint for report in reports}) == 1
    assert len({report.revision_proposals[0].fingerprint for report in reports}) == 1
    assert len({hash(report) for report in reports}) == 1
    assert len({report.model_dump_json() for report in reports}) == 1
    assert request.model_dump(mode="json") == before
