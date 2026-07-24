from __future__ import annotations

import copy
from collections.abc import Sequence

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.integration.context import (
    AgentExecutionResult,
    DebugExecutionEvidence,
    FirmwareExecutionEvidence,
    HardwareExecutionEvidence,
    IntegrationTraceEvent,
    PCBExecutionEvidence,
)
from embedded_copilot.integration.report import (
    DebugReportSection,
    EngineeringReport,
    FirmwareReportSection,
    HardwareReportSection,
    PCBReportSection,
    ReportFinding,
    ReportRecommendation,
    ReportSummary,
)


class ResultAggregator:
    """Aggregate only evidence already projected at the execution boundary."""

    def aggregate(
        self,
        results: Sequence[AgentExecutionResult],
        *,
        trace: Sequence[IntegrationTraceEvent] = (),
    ) -> EngineeringReport:
        isolated = tuple(
            AgentExecutionResult.model_validate(
                copy.deepcopy(item.model_dump(mode="python"))
            )
            for item in results
        )
        names = [item.agent_name.casefold() for item in isolated]
        if len(names) != len(set(names)):
            raise ValueError("integration results contain duplicate agents")

        hardware: HardwareReportSection | None = None
        firmware: FirmwareReportSection | None = None
        pcb: PCBReportSection | None = None
        debug: DebugReportSection | None = None
        recommendations: list[ReportRecommendation] = []
        report_trace = [
            IntegrationTraceEvent.model_validate(
                copy.deepcopy(item.model_dump(mode="python"))
            )
            for item in trace
        ]
        if [item.sequence for item in report_trace] != list(
            range(1, len(report_trace) + 1)
        ):
            raise ValueError("integration trace sequence is invalid")

        for item in isolated:
            report_trace.append(
                IntegrationTraceEvent(
                    sequence=len(report_trace) + 1,
                    stage="agent_executed",
                    status=item.status.value,
                    source_agent=item.agent_name,
                    source_id=item.source_id,
                )
            )
            if item.status is AgentStatus.ERROR:
                continue
            if isinstance(item.result, FirmwareExecutionEvidence):
                firmware = FirmwareReportSection(
                    source_agent="FirmwareAgent",
                    source_id=item.source_id,
                    project_name=item.result.project_name,
                    platform=item.result.platform,
                    framework=item.result.framework,
                    file_paths=item.result.file_paths,
                    structure=item.result.structure,
                )
            elif isinstance(item.result, HardwareExecutionEvidence):
                hardware = HardwareReportSection(
                    source_agent="HardwareAgent",
                    source_id=item.source_id,
                    project_name=item.result.project_name,
                    platform=item.result.platform,
                    mcu=item.result.mcu,
                    components=item.result.components,
                    interfaces=item.result.interfaces,
                    power_requirements=item.result.power_requirements,
                    constraints=item.result.constraints,
                    rationale=item.result.rationale,
                )
            elif isinstance(item.result, PCBExecutionEvidence):
                findings = tuple(
                    ReportFinding(
                        source_agent="PCBAgent",
                        source_id=finding.source_id,
                        category=finding.category,
                        severity=finding.severity,
                        description=finding.description,
                        evidence=finding.evidence,
                        recommendation=finding.recommendation,
                    )
                    for finding in item.result.findings
                )
                pcb = PCBReportSection(
                    source_agent="PCBAgent",
                    source_id=item.source_id,
                    project_name=item.result.project_name,
                    platform=item.result.platform,
                    summary=item.result.summary,
                    findings=findings,
                    passed_rules=item.result.passed_rules,
                    warnings=item.result.warnings,
                )
                recommendations.extend(
                    ReportRecommendation(
                        source_agent=finding.source_agent,
                        source_id=finding.source_id,
                        text=finding.recommendation,
                    )
                    for finding in findings
                )
            elif isinstance(item.result, DebugExecutionEvidence):
                findings = tuple(
                    ReportFinding(
                        source_agent="DebugAgent",
                        source_id=finding.source_id,
                        category=finding.category,
                        severity=finding.severity,
                        description=finding.description,
                        evidence=finding.evidence,
                        recommendation=finding.recommendation,
                    )
                    for finding in item.result.findings
                )
                debug_recommendations = tuple(
                    ReportRecommendation(
                        source_agent="DebugAgent",
                        source_id=recommendation.source_id,
                        text=recommendation.text,
                    )
                    for recommendation in item.result.recommendations
                )
                debug = DebugReportSection(
                    source_agent="DebugAgent",
                    source_id=item.source_id,
                    project_name=item.result.project_name,
                    platform=item.result.platform,
                    error_type=item.result.error_type,
                    summary=item.result.summary,
                    findings=findings,
                    recommendations=debug_recommendations,
                )
                recommendations.extend(
                    ReportRecommendation(
                        source_agent=finding.source_agent,
                        source_id=finding.source_id,
                        text=finding.recommendation,
                    )
                    for finding in findings
                )
                recommendations.extend(debug_recommendations)
            else:
                raise TypeError("integration result is unsupported")

        succeeded = sum(item.status is AgentStatus.SUCCESS for item in isolated)
        failed = len(isolated) - succeeded
        report_source_id = "supervisor:engineering-report"
        report_trace.append(
            IntegrationTraceEvent(
                sequence=len(report_trace) + 1,
                stage="report_aggregated",
                status="error" if failed else "success",
                source_agent="SupervisorAgent",
                source_id=report_source_id,
            )
        )
        return EngineeringReport(
            summary=ReportSummary(
                text=(
                    "Embedded Copilot execution completed: "
                    f"{succeeded} succeeded, {failed} failed."
                ),
                succeeded=succeeded,
                failed=failed,
                source_agent="SupervisorAgent",
                source_id=report_source_id,
            ),
            hardware_section=hardware,
            firmware_section=firmware,
            pcb_section=pcb,
            debug_section=debug,
            recommendations=tuple(recommendations),
            trace=tuple(report_trace),
        )
