from __future__ import annotations

import copy

from pydantic import ValidationError

from embedded_copilot.tool_runtime.audit import emit_audit
from embedded_copilot.tool_runtime.models import (
    CompileFirmwareArguments,
    FirmwareBuildOutput,
    FirmwareTestOutput,
    ReadSerialLogArguments,
    RunFirmwareTestArguments,
    SerialLogOutput,
    ToolAdapterResult,
    ToolAuditEventType,
    ToolExecutionContext,
    ToolPermissionDecision,
    ToolPermissionStatus,
    ToolRequest,
    ToolResult,
    ToolResultStatus,
    tool_request_fingerprint,
)
from embedded_copilot.tool_runtime.ports import (
    ToolAuditSink,
    ToolExecutionPort,
    ToolPermissionPort,
)
from embedded_copilot.tool_runtime.registry import _ToolRegistry


class _ToolExecutionPort:
    __slots__ = ("_audit_sink", "_permission_port", "_registry")

    def __init__(
        self,
        *,
        registry: _ToolRegistry,
        permission_port: ToolPermissionPort,
        audit_sink: ToolAuditSink,
    ) -> None:
        self._registry = registry
        self._permission_port = permission_port
        self._audit_sink = audit_sink

    def execute(self, context: ToolExecutionContext) -> ToolResult:
        context = _validated_context(context)
        request = context.request
        emit_audit(
            self._audit_sink,
            event_type=ToolAuditEventType.TOOL_REQUESTED,
            tool_name=request.tool_name,
            request_id=request.request_id,
            caller=request.caller,
            timestamp=context.requested_at,
        )
        result = self._authorize_and_execute(context)
        emit_audit(
            self._audit_sink,
            event_type={
                ToolResultStatus.SUCCESS: ToolAuditEventType.TOOL_SUCCEEDED,
                ToolResultStatus.FAILED: ToolAuditEventType.TOOL_FAILED,
                ToolResultStatus.REJECTED: ToolAuditEventType.TOOL_REJECTED,
            }[result.status],
            tool_name=request.tool_name,
            request_id=request.request_id,
            caller=request.caller,
            timestamp=context.requested_at,
        )
        return result

    def _authorize_and_execute(self, context: ToolExecutionContext) -> ToolResult:
        request = context.request
        try:
            raw_decision = self._permission_port.authorize(context)
            decision = ToolPermissionDecision.model_validate(
                copy.deepcopy(raw_decision.model_dump(mode="python"))
            )
        except Exception:
            return _result(request, ToolResultStatus.FAILED, "permission_unavailable")
        if not _decision_matches(decision, request):
            return _result(
                request,
                ToolResultStatus.REJECTED,
                "permission_binding_invalid",
            )
        if decision.decision is ToolPermissionStatus.DENIED:
            return _result(request, ToolResultStatus.REJECTED, "permission_denied")
        adapter = self._registry.resolve(request.tool_name)
        if adapter is None:
            return _result(request, ToolResultStatus.REJECTED, "unknown_tool")
        if not _arguments_match(request):
            return _result(request, ToolResultStatus.REJECTED, "arguments_mismatch")
        try:
            raw = adapter.execute(context)
            normalized = ToolAdapterResult.model_validate(
                copy.deepcopy(raw.model_dump(mode="python"))
            )
        except TimeoutError:
            return _result(request, ToolResultStatus.FAILED, "tool_timeout")
        except Exception:
            return _result(request, ToolResultStatus.FAILED, "tool_unavailable")
        if not _output_matches(request, normalized):
            return _result(
                request,
                ToolResultStatus.FAILED,
                "tool_result_rejected",
            )
        return ToolResult(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=normalized.status,
            summary=normalized.summary,
            output=normalized.output,
            artifacts=normalized.artifacts,
            metrics=normalized.metrics,
        )


def create_execution_port(
    *,
    registry: _ToolRegistry,
    permission_port: ToolPermissionPort,
    audit_sink: ToolAuditSink,
) -> ToolExecutionPort:
    return _ToolExecutionPort(
        registry=registry,
        permission_port=permission_port,
        audit_sink=audit_sink,
    )


def _validated_context(value: ToolExecutionContext) -> ToolExecutionContext:
    try:
        return ToolExecutionContext.model_validate(
            copy.deepcopy(value.model_dump(mode="python"))
        )
    except (AttributeError, TypeError, ValidationError):
        raise TypeError("tool execution context is invalid") from None


def _decision_matches(
    decision: ToolPermissionDecision,
    request: ToolRequest,
) -> bool:
    return (
        decision.request_id == request.request_id
        and decision.tool_name == request.tool_name
        and decision.caller == request.caller
        and decision.request_fingerprint == tool_request_fingerprint(request)
    )


def _arguments_match(request: ToolRequest) -> bool:
    expected = {
        "compile_firmware": CompileFirmwareArguments,
        "read_serial_log": ReadSerialLogArguments,
        "run_firmware_test": RunFirmwareTestArguments,
    }.get(request.tool_name)
    return expected is not None and isinstance(request.arguments, expected)


def _output_matches(
    request: ToolRequest,
    result: ToolAdapterResult,
) -> bool:
    if result.status is not ToolResultStatus.SUCCESS:
        return result.output is None
    expected = {
        "compile_firmware": FirmwareBuildOutput,
        "read_serial_log": SerialLogOutput,
        "run_firmware_test": FirmwareTestOutput,
    }.get(request.tool_name)
    return expected is not None and isinstance(result.output, expected)


def _result(
    request: ToolRequest,
    status: ToolResultStatus,
    summary: str,
) -> ToolResult:
    return ToolResult(
        request_id=request.request_id,
        tool_name=request.tool_name,
        status=status,
        summary=summary,
    )
