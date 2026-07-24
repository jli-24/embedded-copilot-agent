from __future__ import annotations

import copy

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.integration.context import (
    IntegrationSourceAgent,
    IntegrationTraceEvent,
)
from embedded_copilot.integration.safety import escape_markdown, is_safe_report_text
from embedded_copilot.schemas.result import ContractModel


def _validated_safe_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not is_safe_report_text(value):
        raise ValueError("report text contains unsafe content")
    return value.strip()


def _validated_safe_items(value: object) -> object:
    if not isinstance(value, (list, tuple)):
        return value
    return tuple(_validated_safe_text(item) for item in value)


class _ReportModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    @field_validator("source_id", mode="before", check_fields=False)
    @classmethod
    def validate_source_id(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if not candidate or len(candidate) > 160 or not is_safe_report_text(candidate):
            raise ValueError("report source id is invalid")
        return candidate


class ReportSummary(_ReportModel):
    text: str = Field(min_length=1)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value


class HardwareReportSection(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    project_name: str | None = None
    platform: str | None = None
    mcu: str | None = None
    components: tuple[str, ...] = ()
    interfaces: tuple[str, ...] = ()
    power_requirements: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    rationale: str | None = None

    @field_validator("project_name", "platform", "mcu", "rationale", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value

    @field_validator(
        "components",
        "interfaces",
        "power_requirements",
        "constraints",
        mode="before",
    )
    @classmethod
    def validate_text_items(cls, value: object) -> object:
        return _validated_safe_items(value)


class FirmwareReportSection(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    project_name: str | None = None
    platform: str | None = None
    framework: str | None = None
    file_paths: tuple[str, ...] = ()
    structure: tuple[str, ...] = ()

    @field_validator("project_name", "platform", "framework", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value

    @field_validator("file_paths", "structure", mode="before")
    @classmethod
    def validate_text_items(cls, value: object) -> object:
        return _validated_safe_items(value)


class ReportFinding(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    category: str
    severity: str
    description: str
    evidence: tuple[str, ...] = ()
    recommendation: str

    @field_validator(
        "category",
        "severity",
        "description",
        "recommendation",
        mode="before",
    )
    @classmethod
    def validate_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, value: object) -> object:
        return _validated_safe_items(value)


class PCBReportSection(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    project_name: str | None = None
    platform: str | None = None
    summary: str | None = None
    findings: tuple[ReportFinding, ...] = ()
    passed_rules: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @field_validator("project_name", "platform", "summary", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value

    @field_validator("passed_rules", "warnings", mode="before")
    @classmethod
    def validate_text_items(cls, value: object) -> object:
        return _validated_safe_items(value)


class ReportRecommendation(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("text", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value


class DebugReportSection(_ReportModel):
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1)
    project_name: str | None = None
    platform: str | None = None
    error_type: str | None = None
    summary: str | None = None
    findings: tuple[ReportFinding, ...] = ()
    recommendations: tuple[ReportRecommendation, ...] = ()

    @field_validator(
        "project_name",
        "platform",
        "error_type",
        "summary",
        mode="before",
    )
    @classmethod
    def validate_optional_text(cls, value: object) -> object:
        return _validated_safe_text(value) if isinstance(value, str) else value


class EngineeringReport(_ReportModel):
    summary: ReportSummary
    hardware_section: HardwareReportSection | None = None
    firmware_section: FirmwareReportSection | None = None
    pcb_section: PCBReportSection | None = None
    debug_section: DebugReportSection | None = None
    recommendations: tuple[ReportRecommendation, ...] = ()
    trace: tuple[IntegrationTraceEvent, ...] = ()

    @model_validator(mode="after")
    def validate_provenance(self) -> "EngineeringReport":
        if not self.trace or [event.sequence for event in self.trace] != list(
            range(1, len(self.trace) + 1)
        ):
            raise ValueError("engineering report trace is invalid")
        report_event = self.trace[-1]
        if (
            report_event.stage != "report_aggregated"
            or self.summary.source_agent != report_event.source_agent
            or self.summary.source_id != report_event.source_id
        ):
            raise ValueError("engineering report summary provenance is invalid")

        execution_sources = {
            (event.source_agent, event.source_id)
            for event in self.trace
            if event.stage == "agent_executed"
        }
        sections = tuple(
            section
            for section in (
                self.hardware_section,
                self.firmware_section,
                self.pcb_section,
                self.debug_section,
            )
            if section is not None
        )
        if any(
            (section.source_agent, section.source_id) not in execution_sources
            for section in sections
        ):
            raise ValueError("engineering report section provenance is invalid")

        findings = tuple(
            finding
            for section in (self.pcb_section, self.debug_section)
            if section is not None
            for finding in section.findings
        )
        for section in (self.pcb_section, self.debug_section):
            if section is None:
                continue
            if any(
                finding.source_agent != section.source_agent
                or not finding.source_id.startswith(f"{section.source_id}#")
                for finding in section.findings
            ):
                raise ValueError("engineering report finding provenance is invalid")
        finding_keys = {
            (finding.source_agent, finding.source_id, finding.recommendation)
            for finding in findings
        }
        if len({finding.source_id for finding in findings}) != len(findings):
            raise ValueError("engineering report finding provenance is ambiguous")
        debug_recommendation_keys = {
            (item.source_agent, item.source_id, item.text)
            for item in (
                self.debug_section.recommendations
                if self.debug_section is not None
                else ()
            )
        }
        if self.debug_section is not None and any(
            item.source_agent != self.debug_section.source_agent
            or not item.source_id.startswith(f"{self.debug_section.source_id}#")
            for item in self.debug_section.recommendations
        ):
            raise ValueError(
                "engineering report recommendation provenance is invalid"
            )
        recommendation_keys = {
            (item.source_agent, item.source_id, item.text)
            for item in self.recommendations
        }
        if not recommendation_keys.issubset(
            finding_keys | debug_recommendation_keys
        ):
            raise ValueError("engineering report recommendation has no source evidence")
        return self


def render_report_json(report: EngineeringReport) -> str:
    validated = EngineeringReport.model_validate(
        copy.deepcopy(report.model_dump(mode="python"))
    )
    return validated.model_dump_json(indent=2)


def render_report_markdown(report: EngineeringReport) -> str:
    validated = EngineeringReport.model_validate(
        copy.deepcopy(report.model_dump(mode="python"))
    )
    lines = [
        "# Embedded Copilot Report",
        "",
        escape_markdown(validated.summary.text),
        _source(validated.summary.source_agent, validated.summary.source_id),
        "",
    ]
    lines.extend(_hardware_markdown(validated.hardware_section))
    lines.extend(_pcb_markdown(validated.pcb_section))
    lines.extend(_firmware_markdown(validated.firmware_section))
    lines.extend(_debug_markdown(validated.debug_section))
    lines.extend(["## Recommendations", ""])
    if validated.recommendations:
        for item in validated.recommendations:
            lines.extend(
                [
                    f"- {escape_markdown(item.text)}",
                    f"  {_source(item.source_agent, item.source_id)}",
                ]
            )
    else:
        lines.append("No Agent recommendation was produced.")
    lines.extend(["", "## Trace", ""])
    for event in validated.trace:
        lines.append(
            f"- {event.sequence}. {event.stage}: {event.status} "
            f"{_source(event.source_agent, event.source_id)}"
        )
    return "\n".join(lines).rstrip() + "\n"


def _source(agent: str, source_id: str) -> str:
    return (
        f"[source_agent: {escape_markdown(agent)}; "
        f"source_id: {escape_markdown(source_id)}]"
    )


def _missing_section(title: str) -> list[str]:
    return [
        f"## {title}",
        "",
        "No validated Agent result was available.",
        _source("SupervisorAgent", "supervisor:engineering-report"),
        "",
    ]


def _display(value: str | None) -> str:
    return escape_markdown(value) if value is not None else "None"


def _display_items(values: tuple[str, ...]) -> str:
    return ", ".join(escape_markdown(value) for value in values) or "None"


def _hardware_markdown(section: HardwareReportSection | None) -> list[str]:
    if section is None:
        return _missing_section("Hardware")
    return [
        "## Hardware",
        "",
        f"- Project: {_display(section.project_name)}",
        f"- Platform: {_display(section.platform)}",
        f"- MCU: {_display(section.mcu)}",
        f"- Components: {_display_items(section.components)}",
        f"- Interfaces: {_display_items(section.interfaces)}",
        f"- Power requirements: {_display_items(section.power_requirements)}",
        f"- Constraints: {_display_items(section.constraints)}",
        f"- Rationale: {_display(section.rationale)}",
        _source(section.source_agent, section.source_id),
        "",
    ]


def _firmware_markdown(section: FirmwareReportSection | None) -> list[str]:
    if section is None:
        return _missing_section("Firmware")
    return [
        "## Firmware",
        "",
        f"- Project: {_display(section.project_name)}",
        f"- Platform: {_display(section.platform)}",
        f"- Framework: {_display(section.framework)}",
        f"- Files: {_display_items(section.file_paths)}",
        f"- Structure: {_display_items(section.structure)}",
        _source(section.source_agent, section.source_id),
        "",
    ]


def _pcb_markdown(section: PCBReportSection | None) -> list[str]:
    if section is None:
        return _missing_section("PCB")
    lines = [
        "## PCB",
        "",
        _display(section.summary),
        _source(section.source_agent, section.source_id),
    ]
    for finding in section.findings:
        lines.extend(
            [
                f"- {escape_markdown(finding.source_id)}: "
                f"{escape_markdown(finding.description)}",
                f"  Evidence: {_display_items(finding.evidence)}",
                f"  Recommendation: {escape_markdown(finding.recommendation)}",
                f"  {_source(finding.source_agent, finding.source_id)}",
            ]
        )
    return [*lines, ""]


def _debug_markdown(section: DebugReportSection | None) -> list[str]:
    if section is None:
        return _missing_section("Debug")
    lines = [
        "## Debug",
        "",
        _display(section.summary),
        _source(section.source_agent, section.source_id),
    ]
    for finding in section.findings:
        lines.extend(
            [
                f"- {escape_markdown(finding.source_id)}: "
                f"{escape_markdown(finding.description)}",
                f"  Evidence: {_display_items(finding.evidence)}",
                f"  Recommendation: {escape_markdown(finding.recommendation)}",
                f"  {_source(finding.source_agent, finding.source_id)}",
            ]
        )
    return [*lines, ""]
