"""Protocol boundaries for Hardware Intelligence composition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.hardware_intelligence.models import (
    DigitalTwinProjection,
    DigitalTwinRequest,
    HardwareAnalysisRequest,
    HardwareIntelligenceSnapshot,
    HardwareObservation,
    HardwareProgressEvent,
    HardwareTelemetryRequest,
    HardwareValidationApproval,
    HardwareValidationProjection,
    HardwareValidationRequest,
)


@runtime_checkable
class HardwareIntelligencePort(Protocol):
    def prepare_hardware_analysis(
        self, request: HardwareAnalysisRequest
    ) -> HardwareIntelligenceSnapshot: ...

    def validate_hardware(
        self,
        snapshot: HardwareIntelligenceSnapshot,
        approval: HardwareValidationApproval,
    ) -> HardwareIntelligenceSnapshot: ...


@runtime_checkable
class DigitalTwinProviderPort(Protocol):
    def simulate(self, request: DigitalTwinRequest) -> DigitalTwinProjection: ...


@runtime_checkable
class HardwareTelemetryPort(Protocol):
    def observe(
        self, request: HardwareTelemetryRequest
    ) -> tuple[HardwareObservation, ...]: ...


@runtime_checkable
class HardwareValidationPort(Protocol):
    def validate(
        self, request: HardwareValidationRequest
    ) -> HardwareValidationProjection: ...


@runtime_checkable
class HardwareProgressSink(Protocol):
    def emit(self, event: HardwareProgressEvent) -> None: ...
