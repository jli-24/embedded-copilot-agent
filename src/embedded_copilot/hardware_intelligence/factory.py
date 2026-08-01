"""Composition root for caller-owned hardware projection ports."""

from embedded_copilot.hardware_intelligence.contracts import (
    DigitalTwinProviderPort,
    HardwareProgressSink,
    HardwareTelemetryPort,
    HardwareValidationPort,
)
from embedded_copilot.hardware_intelligence.facade import HardwareIntelligenceRuntime
from embedded_copilot.hardware_intelligence.runtime import _HardwareIntelligenceService


def create_hardware_intelligence_runtime(
    *,
    twin_provider: DigitalTwinProviderPort,
    telemetry_provider: HardwareTelemetryPort,
    validation_port: HardwareValidationPort,
    progress_sink: HardwareProgressSink,
) -> HardwareIntelligenceRuntime:
    for candidate, contract in (
        (twin_provider, DigitalTwinProviderPort),
        (telemetry_provider, HardwareTelemetryPort),
        (validation_port, HardwareValidationPort),
        (progress_sink, HardwareProgressSink),
    ):
        if not isinstance(candidate, contract):
            raise TypeError("invalid hardware intelligence composition")
    service = _HardwareIntelligenceService(
        twin_provider=twin_provider,
        telemetry_provider=telemetry_provider,
        validation_port=validation_port,
        progress_sink=progress_sink,
    )
    return HardwareIntelligenceRuntime._compose(service)
