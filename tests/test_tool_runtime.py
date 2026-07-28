from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import embedded_copilot.debug_runtime as debug_runtime
import embedded_copilot.tool_runtime as tool_runtime
from embedded_copilot.tool_runtime.adapters import (
    MockBuildScenario,
    MockTestScenario,
    create_mock_firmware_build_adapter,
    create_mock_firmware_test_adapter,
    create_serial_log_adapter,
)

UTC_TIME = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)


class RecordingAuditSink:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.events: list[tool_runtime.ToolAuditEvent] = []
        self._fail_after = fail_after

    def record(self, event: tool_runtime.ToolAuditEvent) -> None:
        if self._fail_after is not None and len(self.events) >= self._fail_after:
            raise RuntimeError(r"C:\private\audit.log")
        self.events.append(event)


class AllowPermission:
    def __init__(self) -> None:
        self.calls: list[tool_runtime.ToolExecutionContext] = []

    def authorize(
        self,
        context: tool_runtime.ToolExecutionContext,
    ) -> tool_runtime.ToolPermissionDecision:
        self.calls.append(context)
        request = context.request
        return tool_runtime.ToolPermissionDecision(
            request_id=request.request_id,
            tool_name=request.tool_name,
            caller=request.caller,
            request_fingerprint=tool_runtime.tool_request_fingerprint(request),
            decision=tool_runtime.ToolPermissionStatus.ALLOWED,
            reason_code=tool_runtime.ToolPermissionReason.AUTHORIZED,
        )


class DenyPermission(AllowPermission):
    def authorize(
        self,
        context: tool_runtime.ToolExecutionContext,
    ) -> tool_runtime.ToolPermissionDecision:
        self.calls.append(context)
        request = context.request
        return tool_runtime.ToolPermissionDecision(
            request_id=request.request_id,
            tool_name=request.tool_name,
            caller=request.caller,
            request_fingerprint=tool_runtime.tool_request_fingerprint(request),
            decision=tool_runtime.ToolPermissionStatus.DENIED,
            reason_code=tool_runtime.ToolPermissionReason.CAPABILITY_DENIED,
        )


class ExplodingPermission:
    def authorize(
        self,
        context: tool_runtime.ToolExecutionContext,
    ) -> tool_runtime.ToolPermissionDecision:
        raise RuntimeError(r"C:\private\policy.json")


class BindingMismatchPermission(AllowPermission):
    def authorize(
        self,
        context: tool_runtime.ToolExecutionContext,
    ) -> tool_runtime.ToolPermissionDecision:
        decision = super().authorize(context)
        return decision.model_copy(update={"caller": "different-caller"})


class StaticAdapter:
    def __init__(
        self,
        tool_name: str,
        result: tool_runtime.ToolAdapterResult | Exception,
    ) -> None:
        self._tool_name = tool_name
        self._result = result
        self.calls: list[tool_runtime.ToolExecutionContext] = []

    @property
    def tool_name(self) -> str:
        return self._tool_name

    def execute(
        self,
        context: tool_runtime.ToolExecutionContext,
    ) -> tool_runtime.ToolAdapterResult:
        self.calls.append(context)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class MutableNameAdapter(StaticAdapter):
    def __init__(
        self,
        tool_name: str,
        result: tool_runtime.ToolAdapterResult,
    ) -> None:
        super().__init__(tool_name, result)
        self.raise_from_name = False

    @property
    def tool_name(self) -> str:
        if self.raise_from_name:
            raise RuntimeError(r"C:\private\adapter.json")
        return self._tool_name


class DebugAuditSink:
    def record(self, event: debug_runtime.DebugAuditEvent) -> None:
        pass


class UARTSource:
    def __init__(self) -> None:
        self.snapshot_calls: list[str] = []

    @property
    def source_type(self) -> debug_runtime.DebugSourceType:
        return debug_runtime.DebugSourceType.UART

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        return _target_identity()

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        self.snapshot_calls.append(target_id)
        return debug_runtime.DebugSourceCapture(
            source_type=debug_runtime.DebugSourceType.UART,
            target_identity=_target_identity(),
            observations=(
                debug_runtime.UARTLogRecord(
                    sequence=2,
                    timestamp=UTC_TIME + timedelta(seconds=2),
                    log_line="error: frame timeout",
                ),
                debug_runtime.UARTLogRecord(
                    sequence=1,
                    timestamp=UTC_TIME + timedelta(seconds=1),
                    log_line="boot complete",
                ),
            ),
            telemetry=(),
        )

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        raise AssertionError("serial adapter must not collect telemetry separately")


class EmptyDebugSource:
    def __init__(self, source_type: debug_runtime.DebugSourceType) -> None:
        self._source_type = source_type

    @property
    def source_type(self) -> debug_runtime.DebugSourceType:
        return self._source_type

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        return _target_identity()

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        return debug_runtime.DebugSourceCapture(
            source_type=self._source_type,
            target_identity=_target_identity(),
            observations=(),
            telemetry=(),
        )

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        return ()


class ReturningDebugPort:
    def __init__(self, snapshot: debug_runtime.FrozenDebugSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def identify_target(
        self,
        request: debug_runtime.TargetIdentificationRequest,
    ) -> debug_runtime.TargetIdentity:
        raise AssertionError("not used")

    def collect_snapshot(
        self,
        request: debug_runtime.DebugSnapshotRequest,
    ) -> debug_runtime.FrozenDebugSnapshot:
        self.calls += 1
        return self.snapshot

    def collect_telemetry(
        self,
        request: debug_runtime.TelemetryRequest,
    ) -> debug_runtime.TelemetrySnapshot:
        raise AssertionError("must not collect telemetry separately")


def _target_identity() -> debug_runtime.TargetIdentity:
    return debug_runtime.TargetIdentity(
        vendor="Espressif",
        family="ESP32",
        architecture="Xtensa",
        device="ESP32",
        core="LX6",
    )


def _compile_arguments() -> tool_runtime.CompileFirmwareArguments:
    return tool_runtime.CompileFirmwareArguments(
        project_id="project:demo",
        build_system=tool_runtime.ToolBuildSystem.ESP_IDF,
        workspace_reference="workspace:demo",
    )


def _context(
    *,
    tool_name: str = "compile_firmware",
    arguments: tool_runtime.ToolArguments | None = None,
    requested_at: datetime = UTC_TIME,
) -> tool_runtime.ToolExecutionContext:
    return tool_runtime.ToolExecutionContext(
        request=tool_runtime.ToolRequest(
            request_id="request:001",
            tool_name=tool_name,
            arguments=arguments or _compile_arguments(),
            caller="supervisor",
        ),
        requested_at=requested_at,
    )


def _runtime(
    adapter: tool_runtime.EngineeringToolPort,
    *,
    permission: tool_runtime.ToolPermissionPort | None = None,
    audit: RecordingAuditSink | None = None,
) -> tuple[
    tool_runtime.ToolExecutionPort,
    tool_runtime.ToolPermissionPort,
    RecordingAuditSink,
]:
    permission = permission or AllowPermission()
    audit = audit or RecordingAuditSink()
    runtime = tool_runtime.create_tool_runtime(
        tools=(adapter,),
        permission_port=permission,
        audit_sink=audit,
    )
    return runtime.tool_port(), permission, audit


def test_public_contract_is_narrow_and_synchronous() -> None:
    assert set(tool_runtime.__all__) == {
        "BuildStatus",
        "CompileFirmwareArguments",
        "EngineeringToolPort",
        "FirmwareBuildOutput",
        "FirmwareTestOutput",
        "ReadSerialLogArguments",
        "RunFirmwareTestArguments",
        "SerialLogLine",
        "SerialLogOutput",
        "SerialSeverity",
        "SerialSeverityCount",
        "SerialSourceType",
        "ToolAdapterResult",
        "ToolArtifactReference",
        "ToolAuditEvent",
        "ToolAuditEventType",
        "ToolAuditSink",
        "ToolAuditUnavailable",
        "ToolBuildSystem",
        "ToolCompiler",
        "ToolExecutionContext",
        "ToolExecutionPort",
        "ToolMetric",
        "ToolMetricUnit",
        "ToolPermissionDecision",
        "ToolPermissionPort",
        "ToolPermissionReason",
        "ToolPermissionStatus",
        "ToolRequest",
        "ToolResult",
        "ToolResultStatus",
        "ToolRuntime",
        "create_tool_runtime",
        "tool_request_fingerprint",
    }
    assert {
        name
        for name, value in tool_runtime.ToolRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"tool_port"}
    assert {
        name
        for name, value in tool_runtime.ToolExecutionPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"execute"}
    assert not inspect.iscoroutinefunction(tool_runtime.ToolExecutionPort.execute)
    for leaked in (
        "registry",
        "executor",
        "adapters",
        "tools",
        "permission_port",
        "audit_sink",
        "settings",
        "configuration",
    ):
        assert not hasattr(tool_runtime.create_tool_runtime, leaked)


def test_contracts_are_frozen_forbid_extra_and_normalize_utc() -> None:
    context = _context(
        requested_at=datetime(
            2026,
            8,
            1,
            11,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )
    )
    assert context.requested_at == UTC_TIME
    with pytest.raises(ValidationError):
        tool_runtime.ToolExecutionContext.model_validate(
            {
                **context.model_dump(mode="python"),
                "command": "make flash",
            }
        )
    with pytest.raises(ValidationError):
        context.request.caller = "changed"
    with pytest.raises(ValidationError):
        tool_runtime.ToolExecutionContext(
            request=context.request,
            requested_at=datetime(2026, 8, 1, 3, 0),
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("project_id", r"C:\project"),
        ("workspace_reference", "../workspace"),
    ),
)
def test_compile_arguments_reject_paths(field: str, value: str) -> None:
    payload = _compile_arguments().model_dump(mode="python")
    payload[field] = value
    with pytest.raises(ValidationError):
        tool_runtime.CompileFirmwareArguments.model_validate(payload)


def test_request_fingerprint_is_stable_and_binds_arguments() -> None:
    request = _context().request
    copied = tool_runtime.ToolRequest.model_validate(request.model_dump(mode="python"))
    changed = request.model_copy(
        update={
            "arguments": request.arguments.model_copy(
                update={"project_id": "project:other"}
            )
        }
    )
    assert tool_runtime.tool_request_fingerprint(request) == (
        tool_runtime.tool_request_fingerprint(copied)
    )
    assert tool_runtime.tool_request_fingerprint(request) != (
        tool_runtime.tool_request_fingerprint(changed)
    )


def test_factory_rejects_invalid_collections_and_duplicate_names() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.REJECTED,
            summary="mock_scenario_not_found",
        ),
    )
    with pytest.raises(TypeError):
        tool_runtime.create_tool_runtime(
            tools=[adapter],  # type: ignore[arg-type]
            permission_port=AllowPermission(),
            audit_sink=RecordingAuditSink(),
        )
    with pytest.raises(ValueError):
        tool_runtime.create_tool_runtime(
            tools=(),
            permission_port=AllowPermission(),
            audit_sink=RecordingAuditSink(),
        )
    with pytest.raises(ValueError):
        tool_runtime.create_tool_runtime(
            tools=(adapter, adapter),
            permission_port=AllowPermission(),
            audit_sink=RecordingAuditSink(),
        )


def test_registry_freezes_validated_name_at_construction() -> None:
    output = tool_runtime.FirmwareBuildOutput(
        build_status=tool_runtime.BuildStatus.SUCCESS,
        compiler=tool_runtime.ToolCompiler.GCC,
        warnings_count=0,
        error_count=0,
        summary="Mock build completed.",
    )
    adapter = MutableNameAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="Mock build completed.",
            output=output,
        ),
    )
    port, _, audit = _runtime(adapter)
    adapter._tool_name = "changed_tool"
    adapter.raise_from_name = True

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.SUCCESS
    assert result.output == output
    assert audit.events[-1].event_type is (
        tool_runtime.ToolAuditEventType.TOOL_SUCCEEDED
    )


def test_permission_denial_prevents_adapter_and_is_audited() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    port, permission, audit = _runtime(adapter, permission=DenyPermission())

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.REJECTED
    assert result.summary == "permission_denied"
    assert result.output is None
    assert adapter.calls == []
    assert len(permission.calls) == 1  # type: ignore[attr-defined]
    assert tuple(event.event_type for event in audit.events) == (
        tool_runtime.ToolAuditEventType.TOOL_REQUESTED,
        tool_runtime.ToolAuditEventType.TOOL_REJECTED,
    )


def test_permission_binding_mismatch_is_rejected() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    port, _, audit = _runtime(adapter, permission=BindingMismatchPermission())

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.REJECTED
    assert result.summary == "permission_binding_invalid"
    assert adapter.calls == []
    assert audit.events[-1].event_type is (
        tool_runtime.ToolAuditEventType.TOOL_REJECTED
    )


def test_permission_exception_is_normalized_without_message_leakage() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    port, _, audit = _runtime(adapter, permission=ExplodingPermission())

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.FAILED
    assert result.summary == "permission_unavailable"
    assert r"C:\private" not in result.model_dump_json()
    assert adapter.calls == []
    assert audit.events[-1].event_type is tool_runtime.ToolAuditEventType.TOOL_FAILED


def test_unknown_tool_is_rejected_after_permission_without_fallback() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    port, permission, audit = _runtime(adapter)

    result = port.execute(_context(tool_name="unknown_tool"))

    assert result.status is tool_runtime.ToolResultStatus.REJECTED
    assert result.summary == "unknown_tool"
    assert adapter.calls == []
    assert len(permission.calls) == 1  # type: ignore[attr-defined]
    assert audit.events[-1].event_type is (
        tool_runtime.ToolAuditEventType.TOOL_REJECTED
    )


def test_argument_type_mismatch_is_rejected() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    port, _, _ = _runtime(adapter)

    result = port.execute(
        _context(
            arguments=tool_runtime.RunFirmwareTestArguments(
                project_id="project:demo",
                test_id="test:smoke",
                workspace_reference="workspace:demo",
            )
        )
    )

    assert result.status is tool_runtime.ToolResultStatus.REJECTED
    assert result.summary == "arguments_mismatch"
    assert adapter.calls == []


def test_requested_audit_failure_prevents_permission_and_adapter() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="must_not_run",
        ),
    )
    permission = AllowPermission()
    port, _, _ = _runtime(
        adapter,
        permission=permission,
        audit=RecordingAuditSink(fail_after=0),
    )

    with pytest.raises(tool_runtime.ToolAuditUnavailable):
        port.execute(_context())

    assert permission.calls == []
    assert adapter.calls == []


def test_terminal_audit_failure_suppresses_result() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.REJECTED,
            summary="mock_scenario_not_found",
        ),
    )
    port, _, audit = _runtime(adapter, audit=RecordingAuditSink(fail_after=1))

    with pytest.raises(tool_runtime.ToolAuditUnavailable):
        port.execute(_context())

    assert len(adapter.calls) == 1
    assert tuple(event.event_type for event in audit.events) == (
        tool_runtime.ToolAuditEventType.TOOL_REQUESTED,
    )


def test_adapter_timeout_and_exception_are_normalized() -> None:
    for exception, summary in (
        (TimeoutError(r"C:\private\build.log"), "tool_timeout"),
        (RuntimeError(r"C:\private\build.log"), "tool_unavailable"),
    ):
        adapter = StaticAdapter("compile_firmware", exception)
        port, _, audit = _runtime(adapter)

        result = port.execute(_context())

        assert result.status is tool_runtime.ToolResultStatus.FAILED
        assert result.summary == summary
        assert r"C:\private" not in result.model_dump_json()
        assert audit.events[-1].event_type is (
            tool_runtime.ToolAuditEventType.TOOL_FAILED
        )


@pytest.mark.parametrize(
    "output",
    (
        None,
        tool_runtime.FirmwareTestOutput(
            passed_count=1,
            failed_count=0,
            duration_ms=1,
            summary="Mock firmware tests completed.",
        ),
    ),
)
def test_success_output_must_match_registered_tool(
    output: tool_runtime.FirmwareTestOutput | None,
) -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="invalid_adapter_output",
            output=output,
        ),
    )
    port, _, audit = _runtime(adapter)

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.FAILED
    assert result.summary == "tool_result_rejected"
    assert result.output is None
    assert audit.events[-1].event_type is tool_runtime.ToolAuditEventType.TOOL_FAILED


def test_mock_build_adapter_requires_exact_scenario_and_marks_mock() -> None:
    adapter = create_mock_firmware_build_adapter(
        scenarios=(
            MockBuildScenario(
                project_id="project:demo",
                build_system=tool_runtime.ToolBuildSystem.ESP_IDF,
                workspace_reference="workspace:demo",
                build_status=tool_runtime.BuildStatus.FAILED,
                compiler=tool_runtime.ToolCompiler.GCC,
                warnings_count=2,
                error_count=1,
                summary="Mock compiler diagnostics collected.",
            ),
        )
    )
    port, _, audit = _runtime(adapter)

    result = port.execute(_context())

    assert result.status is tool_runtime.ToolResultStatus.SUCCESS
    assert isinstance(result.output, tool_runtime.FirmwareBuildOutput)
    assert result.output.execution_mode == "MOCK"
    assert result.output.build_status is tool_runtime.BuildStatus.FAILED
    assert result.output.warnings_count == 2
    assert result.output.error_count == 1
    assert tuple(metric.name for metric in result.metrics) == (
        "error_count",
        "warnings_count",
    )
    assert result.artifacts == ()
    assert audit.events[-1].event_type is (
        tool_runtime.ToolAuditEventType.TOOL_SUCCEEDED
    )

    missing = port.execute(
        _context(
            arguments=_compile_arguments().model_copy(
                update={"project_id": "project:missing"}
            )
        )
    )
    assert missing.status is tool_runtime.ToolResultStatus.REJECTED
    assert missing.summary == "mock_scenario_not_found"
    assert missing.output is None


def test_mock_firmware_test_adapter_uses_exact_binding() -> None:
    adapter = create_mock_firmware_test_adapter(
        scenarios=(
            MockTestScenario(
                project_id="project:demo",
                test_id="test:smoke",
                workspace_reference="workspace:demo",
                passed_count=7,
                failed_count=1,
                duration_ms=125.5,
                summary="Mock firmware tests completed.",
            ),
        )
    )
    port, _, _ = _runtime(adapter)
    context = _context(
        tool_name="run_firmware_test",
        arguments=tool_runtime.RunFirmwareTestArguments(
            project_id="project:demo",
            test_id="test:smoke",
            workspace_reference="workspace:demo",
        ),
    )

    result = port.execute(context)

    assert result.status is tool_runtime.ToolResultStatus.SUCCESS
    assert isinstance(result.output, tool_runtime.FirmwareTestOutput)
    assert result.output.execution_mode == "MOCK"
    assert (result.output.passed_count, result.output.failed_count) == (7, 1)
    assert tuple(metric.name for metric in result.metrics) == (
        "duration_ms",
        "failed_count",
        "passed_count",
    )

    missing = port.execute(
        _context(
            tool_name="run_firmware_test",
            arguments=context.request.arguments.model_copy(
                update={"test_id": "test:other"}
            ),
        )
    )
    assert missing.status is tool_runtime.ToolResultStatus.REJECTED
    assert missing.summary == "mock_scenario_not_found"
    assert missing.output is None


def test_serial_adapter_collects_one_uart_snapshot_and_normalizes_lines() -> None:
    source = UARTSource()
    debug_port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=DebugAuditSink(),
    ).debug_port()
    adapter = create_serial_log_adapter(debug_port=debug_port)
    port, _, audit = _runtime(adapter)
    context = _context(
        tool_name="read_serial_log",
        arguments=tool_runtime.ReadSerialLogArguments(
            target_id="target:esp32",
            source_type=tool_runtime.SerialSourceType.UART,
        ),
    )

    result = port.execute(context)

    assert result.status is tool_runtime.ToolResultStatus.SUCCESS
    assert isinstance(result.output, tool_runtime.SerialLogOutput)
    assert source.snapshot_calls == ["target:esp32"]
    assert tuple(line.sequence for line in result.output.lines) == (1, 2)
    assert tuple(line.severity for line in result.output.lines) == (
        tool_runtime.SerialSeverity.INFO,
        tool_runtime.SerialSeverity.ERROR,
    )
    assert tuple(
        (item.severity, item.count) for item in result.output.severity_summary
    ) == (
        (tool_runtime.SerialSeverity.CRITICAL, 0),
        (tool_runtime.SerialSeverity.ERROR, 1),
        (tool_runtime.SerialSeverity.WARNING, 0),
        (tool_runtime.SerialSeverity.DEBUG, 0),
        (tool_runtime.SerialSeverity.INFO, 1),
    )
    assert audit.events[-1].event_type is (
        tool_runtime.ToolAuditEventType.TOOL_SUCCEEDED
    )


@pytest.mark.parametrize(
    "invalid_binding",
    ("snapshot_id", "source_type", "target_id", "captured_at"),
)
def test_serial_adapter_rejects_snapshot_not_bound_to_request(
    invalid_binding: str,
) -> None:
    source_type = (
        debug_runtime.DebugSourceType.GDB
        if invalid_binding == "source_type"
        else debug_runtime.DebugSourceType.UART
    )
    source = EmptyDebugSource(source_type)
    debug_port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=DebugAuditSink(),
    ).debug_port()
    invalid_snapshot = debug_port.collect_snapshot(
        debug_runtime.DebugSnapshotRequest(
            snapshot_id=(
                "request:stale" if invalid_binding == "snapshot_id" else "request:001"
            ),
            target_id=(
                "target:other" if invalid_binding == "target_id" else "target:esp32"
            ),
            source_type=source_type,
            observed_at=(
                UTC_TIME + timedelta(seconds=1)
                if invalid_binding == "captured_at"
                else UTC_TIME
            ),
        )
    )
    returning = ReturningDebugPort(invalid_snapshot)
    adapter = create_serial_log_adapter(debug_port=returning)
    port, _, audit = _runtime(adapter)

    result = port.execute(
        _context(
            tool_name="read_serial_log",
            arguments=tool_runtime.ReadSerialLogArguments(
                target_id="target:esp32",
                source_type=tool_runtime.SerialSourceType.UART,
            ),
        )
    )

    assert returning.calls == 1
    assert result.status is tool_runtime.ToolResultStatus.FAILED
    assert result.summary == "tool_unavailable"
    assert result.output is None
    assert audit.events[-1].event_type is tool_runtime.ToolAuditEventType.TOOL_FAILED


def test_artifact_metric_and_summary_privacy_validation() -> None:
    with pytest.raises(ValidationError):
        tool_runtime.ToolArtifactReference(
            reference_id=r"C:\firmware.bin",
            artifact_type="firmware",
            status="available",
        )
    with pytest.raises(ValidationError):
        tool_runtime.ToolMetric(
            name="duration",
            value=True,
            unit=tool_runtime.ToolMetricUnit.MILLISECONDS,
        )
    with pytest.raises(ValidationError):
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary=r"Output at C:\private\firmware.bin",
        )
    with pytest.raises(ValidationError):
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="/private",
        )
    with pytest.raises(ValidationError):
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.SUCCESS,
            summary="path=/private",
        )
    request_payload = _context().request.model_dump(mode="python")
    request_payload["caller"] = "sk-abcdefgh"
    with pytest.raises(ValidationError):
        tool_runtime.ToolRequest.model_validate(request_payload)


def test_audit_event_contains_only_allowlisted_metadata() -> None:
    adapter = StaticAdapter(
        "compile_firmware",
        tool_runtime.ToolAdapterResult(
            status=tool_runtime.ToolResultStatus.REJECTED,
            summary="mock_scenario_not_found",
        ),
    )
    port, _, audit = _runtime(adapter)

    port.execute(_context())

    assert len(audit.events) == 2
    for event in audit.events:
        assert set(event.model_dump(mode="json")) == {
            "event_type",
            "tool_name",
            "request_id",
            "caller",
            "timestamp",
        }
        serialized = event.model_dump_json()
        assert "project:demo" not in serialized
        assert "workspace:demo" not in serialized
