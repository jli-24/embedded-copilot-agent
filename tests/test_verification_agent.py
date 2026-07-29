from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

import embedded_copilot.verification_agent as verification
from embedded_copilot.coding_runtime import (
    CodeFileInput,
    HardwareSoftwareFusionRequest,
    PinFunctionCandidate,
    ProjectAnalysisRequest,
    create_coding_runtime,
)
from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    DatasheetContext,
    EngineeringContextResponse,
    EngineeringContextSummary,
)
from embedded_copilot.tool_runtime import (
    BuildStatus,
    FirmwareBuildOutput,
    SerialLogOutput,
    SerialSeverity,
    SerialSeverityCount,
    ToolCompiler,
    ToolMetric,
    ToolMetricUnit,
    ToolResult,
    ToolResultStatus,
)

CONTEXT_ID = "context:0123456789abcdef01234567"
REQUESTED_AT = datetime(2026, 7, 29, 8, 30, tzinfo=timezone.utc)


class RecordingAuditSink:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.events: list[verification.VerificationAuditEvent] = []
        self.fail_after = fail_after

    def record(self, event: verification.VerificationAuditEvent) -> None:
        if self.fail_after is not None and len(self.events) >= self.fail_after:
            raise RuntimeError(r"C:\private\audit.log")
        self.events.append(event)


class StaticChecker:
    def __init__(
        self,
        name: str,
        subject_type: verification.VerificationSubjectType,
        result: verification.VerificationCheckResult | Exception,
    ) -> None:
        self._name = name
        self._subjects = (subject_type,)
        self._result = result
        self.calls: list[verification.VerificationSubject] = []

    @property
    def checker_name(self) -> str:
        return self._name

    @property
    def supported_subjects(
        self,
    ) -> tuple[verification.VerificationSubjectType, ...]:
        return self._subjects

    def verify(
        self,
        subject: verification.VerificationSubject,
    ) -> verification.VerificationCheckResult:
        self.calls.append(subject)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _snapshot(context_id: str = CONTEXT_ID):
    port = create_coding_runtime().coding_port()
    return port.analyze_project(
        ProjectAnalysisRequest(
            context_id=context_id,
            files=(CodeFileInput(path="src/main.c", content="int main(void) {}\n"),),
        )
    ).snapshot


def _fusion(*pin_candidates: PinFunctionCandidate) -> HardwareSoftwareFusionRequest:
    datasheets = tuple(
        DatasheetContext(
            file_id=reference_id,
            component_candidate=ComponentContextCandidate(family="ESP32"),
        )
        for reference_id in ("file:camera", "file:sd")
    )
    return HardwareSoftwareFusionRequest(
        snapshot=_snapshot(),
        engineering_context=EngineeringContextResponse(
            context_summary=EngineeringContextSummary(
                context_id=CONTEXT_ID,
                task_intent="Review simultaneous hardware candidates.",
                datasheets=datasheets,
            )
        ),
        pin_candidates=pin_candidates,
    )


def _firmware_subject(
    *,
    status: BuildStatus = BuildStatus.SUCCESS,
    warnings: int = 0,
    errors: int = 0,
    resources: tuple[verification.FirmwareResourceUsage, ...] = (),
) -> verification.FirmwareVerificationSubject:
    return verification.FirmwareVerificationSubject(
        build_output=FirmwareBuildOutput(
            build_status=status,
            compiler=ToolCompiler.GCC,
            warnings_count=warnings,
            error_count=errors,
            summary="Mock build evidence supplied by Tool Runtime.",
        ),
        resources=resources,
    )


def _request(
    subject: verification.VerificationSubject,
    subject_type: verification.VerificationSubjectType,
    *,
    context_id: str = CONTEXT_ID,
) -> verification.VerificationRequest:
    return verification.VerificationRequest(
        request_id="verification:request-1",
        subject_type=subject_type,
        subject=subject,
        context_id=context_id,
        requested_at=REQUESTED_AT,
    )


def _port(*checkers: verification.VerificationCheckerPort, audit=None):
    sink = audit or RecordingAuditSink()
    agent = verification.create_verification_agent(
        checkers=tuple(checkers),
        audit_sink=sink,
    )
    return agent.verification_port(), sink


def test_factory_and_public_facade_are_narrow() -> None:
    checker = verification.FirmwareVerificationChecker()
    port, _ = _port(checker)

    assert isinstance(port, verification.VerificationPort)
    assert {
        name
        for name, value in verification.VerificationAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"verification_port"}
    assert tuple(
        inspect.signature(verification.create_verification_agent).parameters
    ) == ("checkers", "audit_sink")
    for leaked in (
        "rules",
        "registry",
        "audit",
        "configuration",
        "checker_registry",
    ):
        assert leaked not in verification.__all__

    with pytest.raises(TypeError):
        verification.create_verification_agent(
            checkers=[checker],  # type: ignore[arg-type]
            audit_sink=RecordingAuditSink(),
        )
    with pytest.raises(ValueError):
        verification.create_verification_agent(
            checkers=(),
            audit_sink=RecordingAuditSink(),
        )
    with pytest.raises(ValueError):
        verification.create_verification_agent(
            checkers=(checker, checker),
            audit_sink=RecordingAuditSink(),
        )


def test_contracts_are_frozen_strict_and_revalidated() -> None:
    subject = _firmware_subject()
    request = _request(subject, verification.VerificationSubjectType.FIRMWARE)

    assert request.requested_at == REQUESTED_AT
    with pytest.raises(ValidationError):
        request.context_id = "context:changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        verification.VerificationRequest.model_validate(
            {**request.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        verification.VerificationRequest(
            request_id="verification:naive-time",
            subject_type=verification.VerificationSubjectType.FIRMWARE,
            subject=subject,
            context_id=CONTEXT_ID,
            requested_at=datetime(2026, 7, 29, 8, 30),
        )
    forged = verification.VerificationRequest.model_construct(
        request_id=request.request_id,
        subject_type=verification.VerificationSubjectType.HARDWARE,
        subject=subject,
        context_id=CONTEXT_ID,
        requested_at=REQUESTED_AT,
    )
    port, audit = _port(verification.FirmwareVerificationChecker())
    with pytest.raises(verification.VerificationRequestRejected):
        port.verify(forged)
    assert audit.events == []


def test_firmware_context_and_resource_order_are_bound() -> None:
    snapshot = _snapshot()
    subject = verification.FirmwareVerificationSubject(
        build_output=_firmware_subject().build_output,
        code_context=snapshot,
        resources=(
            verification.FirmwareResourceUsage(
                resource_name="flash", used_bytes=80, limit_bytes=100
            ),
        ),
    )
    _request(subject, verification.VerificationSubjectType.FIRMWARE)

    with pytest.raises(ValidationError, match="context"):
        _request(
            subject,
            verification.VerificationSubjectType.FIRMWARE,
            context_id="context:ffffffffffffffffffffffff",
        )
    with pytest.raises(ValidationError, match="sorted"):
        verification.FirmwareVerificationSubject(
            build_output=subject.build_output,
            resources=(
                verification.FirmwareResourceUsage(
                    resource_name="ram", used_bytes=1, limit_bytes=2
                ),
                verification.FirmwareResourceUsage(
                    resource_name="flash", used_bytes=1, limit_bytes=2
                ),
            ),
        )


@pytest.mark.parametrize(
    ("subject", "expected_status", "category"),
    (
        (_firmware_subject(), verification.VerificationStatus.PASS, None),
        (
            _firmware_subject(status=BuildStatus.FAILED),
            verification.VerificationStatus.FAIL,
            verification.VerificationFindingCategory.BUILD_STATUS,
        ),
        (
            _firmware_subject(errors=1),
            verification.VerificationStatus.FAIL,
            verification.VerificationFindingCategory.BUILD_STATUS,
        ),
        (
            _firmware_subject(warnings=1),
            verification.VerificationStatus.REVIEW_REQUIRED,
            verification.VerificationFindingCategory.BUILD_WARNING,
        ),
    ),
)
def test_firmware_build_rules_are_deterministic(
    subject, expected_status, category
) -> None:
    port, audit = _port(verification.FirmwareVerificationChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.FIRMWARE)
    )

    assert result.status is expected_status
    assert result.confidence == 1.0
    assert result.request_id == "verification:request-1"
    assert all(item.candidate_semantics == "unverified" for item in result.findings)
    if category is not None:
        assert category in {item.category for item in result.findings}
    assert tuple(event.event_type for event in audit.events) == (
        verification.VerificationAuditEventType.VERIFICATION_REQUESTED,
        verification.VerificationAuditEventType.VERIFICATION_COMPLETED,
    )
    assert all(event.timestamp == REQUESTED_AT for event in audit.events)


@pytest.mark.parametrize(
    ("used", "severity"),
    (
        (80, verification.VerificationSeverity.MEDIUM),
        (90, verification.VerificationSeverity.HIGH),
    ),
)
def test_firmware_resource_thresholds_require_review(used, severity) -> None:
    subject = _firmware_subject(
        resources=(
            verification.FirmwareResourceUsage(
                resource_name="flash", used_bytes=used, limit_bytes=100
            ),
        )
    )
    port, _ = _port(verification.FirmwareVerificationChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.FIRMWARE)
    )

    assert result.status is verification.VerificationStatus.REVIEW_REQUIRED
    assert result.findings[0].category is (
        verification.VerificationFindingCategory.RESOURCE_USAGE
    )
    assert result.findings[0].severity is severity


def test_hardware_gpio_conflict_fails_only_the_candidate_proposal() -> None:
    subject = verification.HardwareVerificationSubject(
        fusion_request=_fusion(
            PinFunctionCandidate(
                reference_id="file:camera", pin="PA4", function="CAM_D0"
            ),
            PinFunctionCandidate(reference_id="file:sd", pin="PA4", function="SD_D1"),
        )
    )
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.FAIL
    assert result.findings[0].category is (
        verification.VerificationFindingCategory.PIN_CONFLICT
    )
    assert result.findings[0].candidate_semantics == "unverified"
    serialized = result.model_dump_json().casefold()
    for forbidden in ("fault_confirmed", "hardware_broken", "root_cause"):
        assert forbidden not in serialized


def test_hardware_same_pin_and_function_from_multiple_references_passes() -> None:
    subject = verification.HardwareVerificationSubject(
        fusion_request=_fusion(
            PinFunctionCandidate(
                reference_id="file:camera", pin="PA4", function="SHARED_CLOCK"
            ),
            PinFunctionCandidate(
                reference_id="file:sd", pin="PA4", function="SHARED_CLOCK"
            ),
        )
    )
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.PASS


def test_hardware_interface_and_power_conflicts_are_explicit() -> None:
    camera_d0 = PinFunctionCandidate(
        reference_id="file:camera", pin="PA4", function="D0"
    )
    camera_d0_alternate = PinFunctionCandidate(
        reference_id="file:camera", pin="PA5", function="D0"
    )
    subject = verification.HardwareVerificationSubject(
        fusion_request=_fusion(camera_d0, camera_d0_alternate),
        interface_bindings=(
            verification.InterfaceBindingCandidate(
                reference_id="file:camera",
                interface_id="camera0",
                signal="D0",
                pin="PA4",
            ),
            verification.InterfaceBindingCandidate(
                reference_id="file:camera",
                interface_id="camera0",
                signal="D0",
                pin="PA5",
            ),
        ),
        power_connections=(
            verification.PowerConnectionCandidate(
                source_reference_id="file:camera",
                load_reference_id="file:sd",
                supply_min_v=1.7,
                supply_max_v=1.9,
                required_min_v=3.0,
                required_max_v=3.6,
            ),
        ),
    )
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.FAIL
    assert {item.category for item in result.findings} >= {
        verification.VerificationFindingCategory.INTERFACE_CONFLICT,
        verification.VerificationFindingCategory.POWER_CONSTRAINT,
    }


def test_hardware_touching_power_ranges_are_compatible() -> None:
    subject = verification.HardwareVerificationSubject(
        fusion_request=_fusion(),
        power_connections=(
            verification.PowerConnectionCandidate(
                source_reference_id="file:camera",
                load_reference_id="file:sd",
                supply_min_v=1.8,
                supply_max_v=3.0,
                required_min_v=3.0,
                required_max_v=3.6,
            ),
        ),
    )
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.PASS


def test_hardware_without_checkable_relations_requires_review() -> None:
    subject = verification.HardwareVerificationSubject(fusion_request=_fusion())
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.REVIEW_REQUIRED
    assert result.confidence == 0.5
    assert result.findings[0].category is (
        verification.VerificationFindingCategory.INSUFFICIENT_EVIDENCE
    )


def test_hardware_conflict_evidence_remains_bounded() -> None:
    candidates = tuple(
        PinFunctionCandidate(
            reference_id="file:camera",
            pin="PA4",
            function=f"FUNCTION_{index}",
        )
        for index in range(128)
    )
    subject = verification.HardwareVerificationSubject(
        fusion_request=_fusion(*candidates)
    )
    port, _ = _port(verification.HardwareConstraintChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.HARDWARE)
    )

    assert result.status is verification.VerificationStatus.FAIL
    assert all(len(item) <= 512 for item in result.findings[0].evidence)


def _serial_result() -> ToolResult:
    return ToolResult(
        request_id="tool:request-1",
        tool_name="read_serial_log",
        status=ToolResultStatus.SUCCESS,
        summary="Serial observation completed.",
        output=SerialLogOutput(
            lines=(),
            severity_summary=tuple(
                SerialSeverityCount(severity=severity, count=0)
                for severity in SerialSeverity
            ),
        ),
    )


def test_tool_result_checker_passes_known_non_mock_output() -> None:
    subject = verification.ToolResultVerificationSubject(result=_serial_result())
    port, _ = _port(verification.ToolResultChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.TOOL_RESULT)
    )

    assert result.status is verification.VerificationStatus.PASS
    assert result.findings == ()


@pytest.mark.parametrize(
    "tool_result",
    (
        ToolResult(
            request_id="tool:failed",
            tool_name="read_serial_log",
            status=ToolResultStatus.FAILED,
            summary="tool_unavailable",
        ),
        ToolResult(
            request_id="tool:missing",
            tool_name="read_serial_log",
            status=ToolResultStatus.SUCCESS,
            summary="output_missing",
        ),
        ToolResult(
            request_id="tool:unknown",
            tool_name="unknown_tool",
            status=ToolResultStatus.SUCCESS,
            summary="unknown result",
            output=_serial_result().output,
        ),
        ToolResult(
            request_id="tool:mock",
            tool_name="compile_firmware",
            status=ToolResultStatus.SUCCESS,
            summary="Mock build completed.",
            output=_firmware_subject().build_output,
        ),
    ),
)
def test_untrusted_tool_results_require_review(tool_result: ToolResult) -> None:
    subject = verification.ToolResultVerificationSubject(result=tool_result)
    port, _ = _port(verification.ToolResultChecker())

    result = port.verify(
        _request(subject, verification.VerificationSubjectType.TOOL_RESULT)
    )

    assert result.status is verification.VerificationStatus.REVIEW_REQUIRED
    assert result.findings


def test_forged_tool_metric_is_revalidated_at_request_boundary() -> None:
    forged_metric = ToolMetric.model_construct(
        name="usage",
        value=float("nan"),
        unit=ToolMetricUnit.PERCENT,
    )
    forged_result = ToolResult.model_construct(
        request_id="tool:forged",
        tool_name="read_serial_log",
        status=ToolResultStatus.SUCCESS,
        summary="Forged result.",
        output=_serial_result().output,
        artifacts=(),
        metrics=(forged_metric,),
    )
    forged_subject = verification.ToolResultVerificationSubject.model_construct(
        result=forged_result
    )
    forged_request = verification.VerificationRequest.model_construct(
        request_id="verification:forged",
        subject_type=verification.VerificationSubjectType.TOOL_RESULT,
        subject=forged_subject,
        context_id=CONTEXT_ID,
        requested_at=REQUESTED_AT,
    )
    port, audit = _port(verification.ToolResultChecker())

    with pytest.raises(verification.VerificationRequestRejected):
        port.verify(forged_request)

    assert audit.events == []


def test_checker_results_aggregate_by_worst_status_and_lowest_confidence() -> None:
    pass_checker = StaticChecker(
        "pass_checker",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.PASS,
            findings=(),
            confidence=1.0,
            summary="Verification rules passed.",
        ),
    )
    review_checker = StaticChecker(
        "review_checker",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.REVIEW_REQUIRED,
            findings=(
                verification.VerificationFinding(
                    severity=verification.VerificationSeverity.MEDIUM,
                    category=verification.VerificationFindingCategory.BUILD_WARNING,
                    message="Build warnings require engineer review.",
                    evidence=("observed: warnings_count=1",),
                    recommendation="Review every compiler warning.",
                ),
            ),
            confidence=0.5,
            summary="Engineer review is required.",
        ),
    )
    port, _ = _port(pass_checker, review_checker)

    subject = _firmware_subject()
    result = port.verify(
        _request(subject, verification.VerificationSubjectType.FIRMWARE)
    )

    assert result.status is verification.VerificationStatus.REVIEW_REQUIRED
    assert result.confidence == 0.5
    assert len(pass_checker.calls) == len(review_checker.calls) == 1
    assert pass_checker.calls[0] is not subject
    assert review_checker.calls[0] is not subject
    assert pass_checker.calls[0] is not review_checker.calls[0]


def test_checker_failure_stops_batch_and_suppresses_partial_result() -> None:
    passed = StaticChecker(
        "checker_a",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.PASS,
            findings=(),
            confidence=1.0,
            summary="Verification rules passed.",
        ),
    )
    failed = StaticChecker(
        "checker_b",
        verification.VerificationSubjectType.FIRMWARE,
        RuntimeError(r"C:\private\source.c"),
    )
    skipped = StaticChecker(
        "checker_c",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.PASS,
            findings=(),
            confidence=1.0,
            summary="Must not be delivered.",
        ),
    )
    port, audit = _port(passed, failed, skipped)

    with pytest.raises(verification.VerificationCheckerUnavailable) as captured:
        port.verify(
            _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
        )

    assert r"C:\private" not in str(captured.value)
    assert len(passed.calls) == len(failed.calls) == 1
    assert skipped.calls == []
    assert tuple(event.event_type for event in audit.events) == (
        verification.VerificationAuditEventType.VERIFICATION_REQUESTED,
        verification.VerificationAuditEventType.VERIFICATION_FAILED,
    )


def test_malformed_checker_result_stops_later_checkers() -> None:
    malformed = verification.VerificationCheckResult.model_construct(
        status=verification.VerificationStatus.PASS,
        findings=(
            verification.VerificationFinding(
                severity=verification.VerificationSeverity.MEDIUM,
                category=verification.VerificationFindingCategory.BUILD_WARNING,
                message="This finding makes PASS invalid.",
                evidence=("observed: malformed_checker_result=true",),
                recommendation="Reject the malformed checker output.",
            ),
        ),
        confidence=1.0,
        summary="Malformed result.",
    )
    failed = StaticChecker(
        "checker_a",
        verification.VerificationSubjectType.FIRMWARE,
        malformed,
    )
    skipped = StaticChecker(
        "checker_b",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.PASS,
            findings=(),
            confidence=1.0,
            summary="Must not run.",
        ),
    )
    port, audit = _port(failed, skipped)

    with pytest.raises(verification.VerificationCheckerUnavailable):
        port.verify(
            _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
        )

    assert len(failed.calls) == 1
    assert skipped.calls == []
    assert audit.events[-1].event_type is (
        verification.VerificationAuditEventType.VERIFICATION_FAILED
    )


def test_audit_failures_are_fail_closed() -> None:
    checker = StaticChecker(
        "audit_checker",
        verification.VerificationSubjectType.FIRMWARE,
        verification.VerificationCheckResult(
            status=verification.VerificationStatus.PASS,
            findings=(),
            confidence=1.0,
            summary="Verification rules passed.",
        ),
    )
    requested_failure_port, _ = _port(
        checker,
        audit=RecordingAuditSink(fail_after=0),
    )
    with pytest.raises(verification.VerificationAuditUnavailable):
        requested_failure_port.verify(
            _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
        )
    assert checker.calls == []

    terminal_failure_port, audit = _port(
        checker,
        audit=RecordingAuditSink(fail_after=1),
    )
    with pytest.raises(verification.VerificationAuditUnavailable):
        terminal_failure_port.verify(
            _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
        )
    assert tuple(event.event_type for event in audit.events) == (
        verification.VerificationAuditEventType.VERIFICATION_REQUESTED,
    )


def test_audit_events_are_content_free() -> None:
    port, audit = _port(verification.FirmwareVerificationChecker())

    port.verify(
        _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
    )

    assert set(audit.events[0].model_dump()) == {
        "event_type",
        "request_id",
        "subject_type",
        "timestamp",
    }
    serialized = audit.events[0].model_dump_json().casefold()
    for forbidden in ("source", "content", "hardware", "secret", "path"):
        assert forbidden not in serialized


def test_no_matching_checker_fails_without_partial_result() -> None:
    port, audit = _port(verification.ToolResultChecker())

    with pytest.raises(verification.VerificationCheckerUnavailable):
        port.verify(
            _request(_firmware_subject(), verification.VerificationSubjectType.FIRMWARE)
        )

    assert tuple(event.event_type for event in audit.events) == (
        verification.VerificationAuditEventType.VERIFICATION_REQUESTED,
        verification.VerificationAuditEventType.VERIFICATION_FAILED,
    )
