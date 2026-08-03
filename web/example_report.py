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
            text="ESP32 Camera 工程审查已完成，并保留了可追踪证据。",
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
            components=("Camera 模组", "3.3 V 稳压器"),
            interfaces=("I2C", "SPI"),
            power_requirements=("稳定的 3.3 V 电源轨",),
            constraints=("验证峰值电流裕量",),
            rationale="所选模块覆盖图像采集、控制与稳压供电。",
        ),
        firmware_section=FirmwareReportSection(
            source_agent="FirmwareAgent",
            source_id="agent-result:FirmwareAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            framework="ESP-IDF",
            structure=("Camera 初始化", "帧采集任务"),
        ),
        pcb_section=PCBReportSection(
            source_agent="PCBAgent",
            source_id="agent-result:PCBAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            summary="已审查供电与 Camera 接口布局。",
            findings=(
                ReportFinding(
                    source_agent="PCBAgent",
                    source_id="agent-result:PCBAgent#power-decoupling",
                    category="power_integrity",
                    severity="warning",
                    description="本地去耦电容必须靠近有源器件。",
                    evidence=("已有电源轨连接关系证据。",),
                    recommendation="在 EDA 审查中确认电容布局。",
                ),
            ),
            passed_rules=("连接关系证据可追踪",),
        ),
        debug_section=DebugReportSection(
            source_agent="DebugAgent",
            source_id="agent-result:DebugAgent",
            project_name="ESP32 Camera",
            platform="ESP32",
            error_type="compile_error",
            summary="示例编译问题已定位到符号链接证据。",
            findings=(
                ReportFinding(
                    source_agent="DebugAgent",
                    source_id="agent-result:DebugAgent#symbol-linkage",
                    category="linkage",
                    severity="error",
                    description="必要的应用入口符号未解析。",
                    evidence=("Linker 报告入口符号未解析。",),
                    recommendation="检查组件注册与入口符号归属。",
                ),
            ),
        ),
        trace=tuple(trace),
    )
