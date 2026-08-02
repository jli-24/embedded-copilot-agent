from __future__ import annotations

import pytest

from embedded_copilot.engineering_execution import (
    EngineeringExecutionRejected,
    EngineeringExecutionState,
    ExecutionFindingCode,
    create_engineering_execution_runtime,
)
from tests.engineering_execution.conftest import make_request
from tests.engineering_execution.test_runtime import BuildPortFake


class ExceptionPort(BuildPortFake):
    def build(self, request):
        self.calls.append(request)
        raise RuntimeError("C:\\secret\\build stdout token=private")


class MalformedPort(BuildPortFake):
    def build(self, request):
        self.calls.append(request)
        return object()


class MutationPort(BuildPortFake):
    def build(self, request):
        object.__setattr__(
            request.artifact,
            "artifact_source_fingerprint",
            "sha256:" + "0" * 64,
        )
        return super().build(request)


def test_binding_mismatch_is_rejected_without_port_call(artifact_report) -> None:
    request = make_request(artifact_report)
    forged = request.model_copy(
        update={"artifact_source_fingerprint": "sha256:" + "0" * 64},
        deep=True,
    )
    port = BuildPortFake()
    with pytest.raises(EngineeringExecutionRejected, match="request rejected"):
        create_engineering_execution_runtime(
            build_port=port
        ).engineering_execution_port().execute(forged)
    assert not port.calls


@pytest.mark.parametrize("port_type", (ExceptionPort, MalformedPort))
def test_adapter_failure_is_sanitized(port_type, artifact_report) -> None:
    port = port_type()
    report = (
        create_engineering_execution_runtime(build_port=port)
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert report.execution_status is EngineeringExecutionState.FAILED
    serialized = report.model_dump_json().casefold()
    assert "secret" not in serialized
    assert "stdout" not in serialized
    assert "token" not in serialized


def test_adapter_cannot_mutate_runtime_artifact_binding(artifact_report) -> None:
    request = make_request(artifact_report)
    before = request.model_dump(mode="python")
    report = (
        create_engineering_execution_runtime(build_port=MutationPort())
        .engineering_execution_port()
        .execute(request)
    )
    assert report.execution_status is EngineeringExecutionState.FAILED
    assert ExecutionFindingCode.ARTIFACT_MUTATED in report.review.finding_codes
    assert request.model_dump(mode="python") == before
