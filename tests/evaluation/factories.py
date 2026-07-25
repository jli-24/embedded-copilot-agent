from __future__ import annotations

from embedded_copilot.integration.context import IntegrationTraceEvent
from embedded_copilot.integration.report import (
    DebugReportSection,
    EngineeringReport,
    FirmwareReportSection,
    HardwareReportSection,
    PCBReportSection,
    ReportSummary,
)


def engineering_report(
    *,
    planned: tuple[str, ...] = ("FirmwareAgent", "HardwareAgent"),
    successful: tuple[str, ...] = ("FirmwareAgent", "HardwareAgent"),
    include_firmware: bool = True,
    include_hardware: bool = True,
    include_pcb: bool = False,
    include_debug: bool = False,
) -> EngineeringReport:
    trace: list[IntegrationTraceEvent] = [
        IntegrationTraceEvent(
            sequence=1,
            stage="input_analyzed",
            status="success",
            source_agent="SupervisorAgent",
            source_id="supervisor:input-analysis",
        )
    ]
    for agent_name in planned:
        trace.append(
            IntegrationTraceEvent(
                sequence=len(trace) + 1,
                stage="agent_planned",
                status="success",
                source_agent="SupervisorAgent",
                source_id=f"supervisor:plan:{agent_name}",
            )
        )
    for agent_name in planned:
        trace.append(
            IntegrationTraceEvent(
                sequence=len(trace) + 1,
                stage="agent_executed",
                status="success" if agent_name in successful else "error",
                source_agent=agent_name,  # type: ignore[arg-type]
                source_id=f"agent-result:{agent_name}",
            )
        )
    trace.append(
        IntegrationTraceEvent(
            sequence=len(trace) + 1,
            stage="report_aggregated",
            status="success",
            source_agent="SupervisorAgent",
            source_id="supervisor:engineering-report",
        )
    )
    return EngineeringReport(
        summary=ReportSummary(
            text="Synthetic evaluation completed.",
            succeeded=len(successful),
            failed=len(planned) - len(successful),
            source_agent="SupervisorAgent",
            source_id="supervisor:engineering-report",
        ),
        firmware_section=(
            FirmwareReportSection(
                source_agent="FirmwareAgent",
                source_id="agent-result:FirmwareAgent",
                project_name="Synthetic firmware",
                platform="ESP32",
                framework="ESP-IDF",
            )
            if include_firmware
            else None
        ),
        hardware_section=(
            HardwareReportSection(
                source_agent="HardwareAgent",
                source_id="agent-result:HardwareAgent",
                project_name="Synthetic hardware",
                platform="ESP32",
                mcu="ESP32",
            )
            if include_hardware
            else None
        ),
        pcb_section=(
            PCBReportSection(
                source_agent="PCBAgent",
                source_id="agent-result:PCBAgent",
                project_name="Synthetic PCB",
                platform="ESP32",
                summary="Synthetic PCB review completed.",
            )
            if include_pcb
            else None
        ),
        debug_section=(
            DebugReportSection(
                source_agent="DebugAgent",
                source_id="agent-result:DebugAgent",
                project_name="Synthetic debug",
                platform="ESP32",
                error_type="compile_error",
                summary="Synthetic debug review completed.",
            )
            if include_debug
            else None
        ),
        trace=tuple(trace),
    )
