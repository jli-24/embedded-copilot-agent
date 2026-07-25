from __future__ import annotations

from embedded_copilot.integration.context import IntegrationTraceEvent
from embedded_copilot.integration.report import (
    DebugReportSection,
    EngineeringReport,
    FirmwareReportSection,
    HardwareReportSection,
    PCBReportSection,
    ReportFinding,
    ReportSummary,
)


def create_esp32_camera_example_report() -> EngineeringReport:
    agents = ("HardwareAgent", "FirmwareAgent", "PCBAgent", "DebugAgent")
    trace: list[IntegrationTraceEvent] = [
        IntegrationTraceEvent(
            sequence=1,
            stage="input_analyzed",
            status="success",
            source_agent="SupervisorAgent",
            source_id="supervisor:input-analysis",
        )
    ]
    for agent_name in agents:
        trace.append(
            IntegrationTraceEvent(
                sequence=len(trace) + 1,
                stage="agent_planned",
                status="success",
                source_agent="SupervisorAgent",
                source_id=f"supervisor:plan:{agent_name}",
            )
        )
    for agent_name in agents:
        trace.append(
            IntegrationTraceEvent(
                sequence=len(trace) + 1,
                stage="agent_executed",
                status="success",
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
            text="ESP32 camera engineering review completed with traceable evidence.",
            succeeded=4,
            failed=0,
            source_agent="SupervisorAgent",
            source_id="supervisor:engineering-report",
        ),
        hardware_section=HardwareReportSection(
            source_agent="HardwareAgent",
            source_id="agent-result:HardwareAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            mcu="ESP32",
            components=("Camera module", "3.3 V regulator"),
            interfaces=("I2C", "SPI"),
            power_requirements=("Stable 3.3 V rail",),
            constraints=("Validate peak current margin",),
            rationale="The selected blocks cover capture, control, and regulated power.",
        ),
        firmware_section=FirmwareReportSection(
            source_agent="FirmwareAgent",
            source_id="agent-result:FirmwareAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            framework="ESP-IDF",
            structure=("Camera initialization", "Frame capture task"),
        ),
        pcb_section=PCBReportSection(
            source_agent="PCBAgent",
            source_id="agent-result:PCBAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            summary="Power delivery and camera interface placement were reviewed.",
            findings=(
                ReportFinding(
                    source_agent="PCBAgent",
                    source_id="agent-result:PCBAgent#power-decoupling",
                    category="power_integrity",
                    severity="warning",
                    description="Local decoupling must remain close to active devices.",
                    evidence=("Power rail connectivity evidence is available.",),
                    recommendation="Confirm capacitor placement during EDA review.",
                ),
            ),
            passed_rules=("Connectivity evidence is traceable",),
        ),
        debug_section=DebugReportSection(
            source_agent="DebugAgent",
            source_id="agent-result:DebugAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            error_type="compile_error",
            summary="The example compile issue is isolated to symbol linkage evidence.",
            findings=(
                ReportFinding(
                    source_agent="DebugAgent",
                    source_id="agent-result:DebugAgent#symbol-linkage",
                    category="linkage",
                    severity="error",
                    description="A required application entry symbol was unresolved.",
                    evidence=("The linker reported an unresolved entry symbol.",),
                    recommendation="Verify component registration and entry symbol ownership.",
                ),
            ),
        ),
        trace=tuple(trace),
    )
