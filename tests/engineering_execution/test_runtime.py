from __future__ import annotations

from embedded_copilot.engineering_execution import (
    BuildResultStatus,
    EngineeringExecutionState,
    ExecutionApprovalStatus,
    ExecutionFindingCode,
    ExecutionPolicyStatus,
    ExecutionToolType,
    create_engineering_execution_runtime,
)
from tests.engineering_execution.conftest import make_metadata, make_request


class BuildPortFake:
    def __init__(self, status=BuildResultStatus.SUCCESS) -> None:
        self._metadata = make_metadata()
        self.status = status
        self.metadata_reads = 0
        self.calls = []

    @property
    def metadata(self):
        self.metadata_reads += 1
        return self._metadata

    def build(self, request):
        from embedded_copilot.engineering_execution import (
            BuildResult,
            build_result_fingerprint,
        )

        self.calls.append(request)
        findings = (
            ("BUILD_DOMAIN_FAILED",) if self.status is BuildResultStatus.FAILED else ()
        )
        values = dict(
            artifact_fingerprint=request.artifact.artifact_fingerprint,
            tool_type=ExecutionToolType.BUILD_ADAPTER,
            status=self.status,
            finding_codes=findings,
        )
        return BuildResult(
            **values,
            fingerprint=build_result_fingerprint(**values),
        )


class MetadataFailurePort(BuildPortFake):
    @property
    def metadata(self):
        self.metadata_reads += 1
        raise RuntimeError("provider path and credential must stay private")


def test_build_success_executes_once_and_preserves_state_history(
    artifact_report,
) -> None:
    build = BuildPortFake()
    report = (
        create_engineering_execution_runtime(build_port=build)
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert report.execution_status is EngineeringExecutionState.EXECUTED
    assert report.review.state_history == (
        EngineeringExecutionState.PROPOSED,
        EngineeringExecutionState.APPROVED,
        EngineeringExecutionState.EXECUTED,
    )
    assert report.result.status is BuildResultStatus.SUCCESS
    assert len(build.calls) == 1
    assert build.metadata_reads == 1


def test_domain_failure_is_executed_but_not_claimed_successful(artifact_report) -> None:
    build = BuildPortFake(BuildResultStatus.FAILED)
    report = (
        create_engineering_execution_runtime(build_port=build)
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert report.execution_status is EngineeringExecutionState.EXECUTED
    assert report.result.status is BuildResultStatus.FAILED
    assert ExecutionFindingCode.BUILD_FAILED in report.review.finding_codes
    assert report.candidate_semantics == "unverified"
    assert report.review_required is True


def test_pending_rejected_and_blocked_policy_never_touch_adapter(
    artifact_report,
) -> None:
    for kwargs in (
        {"approval_status": ExecutionApprovalStatus.PENDING},
        {"approval_status": ExecutionApprovalStatus.REJECTED},
        {"policy_status": ExecutionPolicyStatus.BLOCKED},
    ):
        build = BuildPortFake()
        report = (
            create_engineering_execution_runtime(build_port=build)
            .engineering_execution_port()
            .execute(make_request(artifact_report, **kwargs))
        )
        assert report.execution_status is EngineeringExecutionState.BLOCKED
        assert not build.calls
        assert build.metadata_reads == 0


def test_missing_port_returns_failed_unavailable_without_fallback(
    artifact_report,
) -> None:
    report = (
        create_engineering_execution_runtime()
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert report.execution_status is EngineeringExecutionState.FAILED
    assert report.result.status is BuildResultStatus.UNAVAILABLE
    assert (
        ExecutionFindingCode.EXECUTION_PORT_UNAVAILABLE in report.review.finding_codes
    )


def test_adapter_binding_and_metadata_failure_are_safe(artifact_report) -> None:
    cases = (
        (
            BuildPortFake(),
            make_request(artifact_report, adapter_binding_id="different-adapter"),
        ),
        (MetadataFailurePort(), make_request(artifact_report)),
    )
    for port, request in cases:
        report = (
            create_engineering_execution_runtime(build_port=port)
            .engineering_execution_port()
            .execute(request)
        )
        assert report.execution_status is EngineeringExecutionState.FAILED
        assert not port.calls
        assert "provider" not in report.model_dump_json().casefold()


def test_port_reported_unavailable_is_top_level_failed(artifact_report) -> None:
    build = BuildPortFake(BuildResultStatus.UNAVAILABLE)
    report = (
        create_engineering_execution_runtime(build_port=build)
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert report.execution_status is EngineeringExecutionState.FAILED
    assert report.result.status is BuildResultStatus.UNAVAILABLE
    assert len(build.calls) == 1


def test_approval_expired_is_not_emitted_in_v055(artifact_report) -> None:
    report = (
        create_engineering_execution_runtime(build_port=BuildPortFake())
        .engineering_execution_port()
        .execute(make_request(artifact_report))
    )
    assert ExecutionFindingCode.APPROVAL_EXPIRED not in report.review.finding_codes
