from __future__ import annotations

import copy
from datetime import datetime
from typing import NoReturn, Protocol, TypeVar, cast

from pydantic import BaseModel
from pydantic import ValidationError

from embedded_copilot.debug_runtime.adapters.gdb import GDBDebugAdapter
from embedded_copilot.debug_runtime.adapters.jlink import JLinkDebugAdapter
from embedded_copilot.debug_runtime.adapters.stlink import STLinkDebugAdapter
from embedded_copilot.debug_runtime.adapters.uart import UARTDebugAdapter
from embedded_copilot.debug_runtime.audit import emit_audit
from embedded_copilot.debug_runtime.exceptions import (
    DebugAuditUnavailable,
    DebugObservationRejected,
    DebugObservationTimeout,
    DebugSourceUnavailable,
)
from embedded_copilot.debug_runtime.models import (
    DebugAuditEventType,
    DebugSnapshotRequest,
    DebugSourceType,
    FrozenDebugSnapshot,
    TargetIdentificationRequest,
    TargetIdentity,
    TelemetryRequest,
    TelemetrySnapshot,
)
from embedded_copilot.debug_runtime.ports import (
    DebugAuditSink,
    DebugPort,
    DebugSourcePort,
)

_RequestT = TypeVar(
    "_RequestT",
    TargetIdentificationRequest,
    DebugSnapshotRequest,
    TelemetryRequest,
)


class _DebugAdapter(Protocol):
    @property
    def source_type(self) -> DebugSourceType: ...

    def identify(self, target_id: str) -> TargetIdentity: ...

    def snapshot(self, request: DebugSnapshotRequest) -> FrozenDebugSnapshot: ...

    def telemetry(
        self,
        target_id: str,
        captured_at: datetime,
    ) -> TelemetrySnapshot: ...


class DebugRuntime:
    __slots__ = ("_debug_port",)

    def __init__(self, debug_port: DebugPort) -> None:
        raise TypeError("DebugRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, debug_port: DebugPort) -> "DebugRuntime":
        if not isinstance(debug_port, DebugPort):
            raise TypeError("debug port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_debug_port", debug_port)
        return runtime

    def debug_port(self) -> DebugPort:
        return self._debug_port


class _DebugPort:
    __slots__ = ("_adapters", "_audit_sink")

    def __init__(
        self,
        adapters: tuple[_DebugAdapter, ...],
        audit_sink: DebugAuditSink,
    ) -> None:
        self._adapters = adapters
        self._audit_sink = audit_sink

    def identify_target(
        self,
        request: TargetIdentificationRequest,
    ) -> TargetIdentity:
        request = _validated_request(TargetIdentificationRequest, request)
        success = DebugAuditEventType.TARGET_IDENTIFIED
        failure = DebugAuditEventType.TARGET_IDENTIFICATION_FAILED
        try:
            result = self._adapter(request.source_type).identify(request.target_id)
        except Exception as exc:
            _failed(self._audit_sink, request, failure, exc)
        emit_audit(
            self._audit_sink,
            event_type=success,
            target_id=request.target_id,
            source_type=request.source_type,
            timestamp=request.observed_at,
        )
        return result

    def collect_snapshot(
        self,
        request: DebugSnapshotRequest,
    ) -> FrozenDebugSnapshot:
        request = _validated_request(DebugSnapshotRequest, request)
        success = DebugAuditEventType.SNAPSHOT_COLLECTED
        failure = DebugAuditEventType.SNAPSHOT_COLLECTION_FAILED
        try:
            result = self._adapter(request.source_type).snapshot(request)
        except Exception as exc:
            _failed(self._audit_sink, request, failure, exc)
        emit_audit(
            self._audit_sink,
            event_type=success,
            target_id=request.target_id,
            source_type=request.source_type,
            timestamp=request.observed_at,
        )
        return result

    def collect_telemetry(
        self,
        request: TelemetryRequest,
    ) -> TelemetrySnapshot:
        request = _validated_request(TelemetryRequest, request)
        success = DebugAuditEventType.TELEMETRY_COLLECTED
        failure = DebugAuditEventType.TELEMETRY_COLLECTION_FAILED
        try:
            adapter = self._adapter(request.source_type)
            result = adapter.telemetry(request.target_id, request.observed_at)
        except Exception as exc:
            _failed(self._audit_sink, request, failure, exc)
        emit_audit(
            self._audit_sink,
            event_type=success,
            target_id=request.target_id,
            source_type=request.source_type,
            timestamp=request.observed_at,
        )
        return result

    def _adapter(self, source_type: DebugSourceType) -> _DebugAdapter:
        for adapter in self._adapters:
            if adapter.source_type is source_type:
                return adapter
        raise DebugSourceUnavailable


def create_debug_runtime(
    *,
    sources: tuple[DebugSourcePort, ...],
    audit_sink: DebugAuditSink,
) -> DebugRuntime:
    if not isinstance(sources, tuple):
        raise TypeError("sources must be a tuple")
    if not sources:
        raise ValueError("sources must not be empty")
    if not isinstance(audit_sink, DebugAuditSink):
        raise TypeError("audit sink is invalid")
    adapters: list[_DebugAdapter] = []
    source_types: list[DebugSourceType] = []
    for source in sources:
        try:
            source_is_valid = isinstance(source, DebugSourcePort)
        except Exception:
            raise TypeError("debug source type is invalid") from None
        if not source_is_valid:
            raise TypeError("debug source is invalid")
        try:
            source_type = DebugSourceType(source.source_type)
        except Exception:
            raise TypeError("debug source type is invalid") from None
        source_types.append(source_type)
        adapter_type = {
            DebugSourceType.UART: UARTDebugAdapter,
            DebugSourceType.JLINK: JLinkDebugAdapter,
            DebugSourceType.STLINK: STLinkDebugAdapter,
            DebugSourceType.GDB: GDBDebugAdapter,
        }[source_type]
        adapters.append(cast(_DebugAdapter, adapter_type(source, source_type)))
    if len(source_types) != len(set(source_types)):
        raise ValueError("source types must be unique")
    return DebugRuntime._compose(_DebugPort(tuple(adapters), audit_sink))


def _validated_request(
    model_type: type[_RequestT],
    value: BaseModel,
) -> _RequestT:
    try:
        return model_type.model_validate(copy.deepcopy(value.model_dump(mode="python")))
    except (AttributeError, TypeError, ValidationError):
        raise DebugObservationRejected from None


def _failed(
    sink: DebugAuditSink,
    request: TargetIdentificationRequest,
    event_type: DebugAuditEventType,
    error: Exception,
) -> NoReturn:
    emit_audit(
        sink,
        event_type=event_type,
        target_id=request.target_id,
        source_type=request.source_type,
        timestamp=request.observed_at,
    )
    if isinstance(error, DebugAuditUnavailable):
        raise error
    if isinstance(error, DebugObservationRejected):
        raise error
    if isinstance(error, TimeoutError):
        raise DebugObservationTimeout from None
    if isinstance(error, DebugSourceUnavailable):
        raise error
    raise DebugSourceUnavailable from None
