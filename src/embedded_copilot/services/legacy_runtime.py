from __future__ import annotations

from embedded_copilot.services.analysis import AnalysisService
from embedded_copilot.services.config import Settings
from embedded_copilot.services.execution import ExecutionRegistry
from embedded_copilot.debug.agent import DebugAgent as FoundationDebugAgent
from embedded_copilot.firmware.agent import FirmwareAgent as FoundationFirmwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.supervisor.agent import SupervisorAgent

LEGACY_RUNTIME_AGENT_TYPES = (
    SupervisorAgent,
    FoundationFirmwareAgent,
    FoundationDebugAgent,
    HardwareAgent,
    PCBAgent,
)


def build_legacy_runtime(settings: Settings) -> AnalysisService:
    """Compose the legacy analysis pipeline for backward-compatible APIs."""
    from embedded_copilot.datasheet.extensions.real_pdf.parser import (
        RealPDFDatasheetParser,
    )
    from embedded_copilot.engineering.adapter import (
        EngineeringSupervisorAdapter,
        RealEngineeringInputAdapter,
    )
    from embedded_copilot.engineering.agent_adapters import (
        ExtensionMetadataSanitizingAgentAdapter,
        FirmwareAgentInputAdapter,
        HardwareAgentInputAdapter,
    )
    from embedded_copilot.engineering.config import (
        EngineeringExtensionSettings,
        real_pdf_backend_available,
    )
    from embedded_copilot.engineering.resolver import TrustedEngineeringResolver
    from embedded_copilot.hardware_design.adapter import (
        HardwareBlueprintProjectionAgentAdapter,
    )

    extension = EngineeringExtensionSettings.from_environment()
    supervisor: object = SupervisorAgent(
        agents=(
            FoundationFirmwareAgent(),
            HardwareBlueprintProjectionAgentAdapter(HardwareAgent()),
            PCBAgent(),
            FoundationDebugAgent(),
        )
    )
    if extension.input_root is not None and real_pdf_backend_available():
        supervisor = EngineeringSupervisorAdapter(
            delegate=SupervisorAgent(
                agents=(
                    FirmwareAgentInputAdapter(FoundationFirmwareAgent()),
                    HardwareBlueprintProjectionAgentAdapter(
                        HardwareAgentInputAdapter(HardwareAgent())
                    ),
                    ExtensionMetadataSanitizingAgentAdapter(PCBAgent()),
                    ExtensionMetadataSanitizingAgentAdapter(FoundationDebugAgent()),
                )
            ),
            input_adapter=RealEngineeringInputAdapter(
                resolver=TrustedEngineeringResolver(extension.input_root),
                pdf_parser=RealPDFDatasheetParser(),
            ),
        )
    return AnalysisService(
        supervisor=supervisor,
        registry=ExecutionRegistry(capacity=settings.analysis_registry_capacity),
        timeout_seconds=settings.analysis_timeout_seconds,
    )


__all__ = ["LEGACY_RUNTIME_AGENT_TYPES", "build_legacy_runtime"]
