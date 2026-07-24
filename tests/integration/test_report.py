from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.debug.models import DebugFinding, DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.integration.aggregator import ResultAggregator
from embedded_copilot.integration.context import AgentExecutionResult
from embedded_copilot.integration.report import (
    EngineeringReport,
    render_report_json,
    render_report_markdown,
)
from embedded_copilot.pcb.models import PCBIssue, PCBReviewReport


def _results() -> tuple[AgentExecutionResult, ...]:
    return (
        AgentExecutionResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            result=FirmwareProject(
                name="camera",
                platform="ESP32",
                framework="ESP-IDF",
                files=[
                    ProjectFile(
                        path="main/main.c",
                        content="SECRET_FIRMWARE_BODY",
                        language="C",
                    )
                ],
                structure=["main"],
            ),
        ),
        AgentExecutionResult(
            agent_name="HardwareAgent",
            status=AgentStatus.SUCCESS,
            result=HardwarePlan(
                project_name="camera",
                platform="ESP32",
                mcu="ESP32-S3",
                components=[
                    HardwareComponent(
                        name="OV2640",
                        category="camera",
                        interface=["DVP"],
                        description="Camera sensor selected by the agent.",
                    )
                ],
                interfaces=["DVP"],
                power_requirements=["3.3 V"],
                constraints=["offline"],
                rationale="Existing hardware evidence.",
            ),
        ),
        AgentExecutionResult(
            agent_name="PCBAgent",
            status=AgentStatus.SUCCESS,
            result=PCBReviewReport(
                project_name="camera",
                platform="ESP32",
                issues=[
                    PCBIssue(
                        id="pcb-power-1",
                        category="power",
                        severity="warning",
                        description="Power evidence observed.",
                        recommendation="Review the existing power evidence.",
                        evidence=["3V3 net exists"],
                    )
                ],
                summary="Existing PCB summary.",
            ),
        ),
        AgentExecutionResult(
            agent_name="DebugAgent",
            status=AgentStatus.SUCCESS,
            result=DebugReport(
                project_name="camera",
                platform="ESP32",
                error_type="compile_error",
                summary="Existing debug summary.",
                findings=[
                    DebugFinding(
                        id="debug-1",
                        category="compiler",
                        severity="error",
                        description="Undefined symbol observed.",
                        evidence=["undefined reference"],
                        recommendation="Link the existing implementation.",
                    )
                ],
                recommendations=["Re-run the existing build."],
            ),
        ),
    )


def test_aggregator_projects_only_existing_evidence_with_provenance() -> None:
    report = ResultAggregator().aggregate(_results())

    assert isinstance(report, EngineeringReport)
    assert report.hardware_section is not None
    assert report.hardware_section.source_agent == "HardwareAgent"
    assert report.hardware_section.source_id == "agent-result:HardwareAgent"
    assert report.firmware_section is not None
    assert report.firmware_section.file_paths == ("main/main.c",)
    assert report.pcb_section is not None
    assert report.pcb_section.findings[0].source_id == (
        "agent-result:PCBAgent#pcb-power-1"
    )
    assert report.debug_section is not None
    assert report.debug_section.findings[0].source_id == (
        "agent-result:DebugAgent#debug-1"
    )
    assert [item.text for item in report.recommendations] == [
        "Review the existing power evidence.",
        "Link the existing implementation.",
        "Re-run the existing build.",
    ]
    assert all(item.source_agent for item in report.recommendations)
    assert all(item.source_id for item in report.recommendations)


def test_report_rendering_is_deterministic_and_redacts_raw_content() -> None:
    report = ResultAggregator().aggregate(_results())

    first_json = render_report_json(report)
    second_json = render_report_json(report.model_copy(deep=True))
    first_markdown = render_report_markdown(report)
    second_markdown = render_report_markdown(report.model_copy(deep=True))

    assert first_json == second_json
    assert first_markdown == second_markdown
    assert first_markdown.startswith("# Embedded Copilot Report\n")
    assert "## Hardware" in first_markdown
    assert "## PCB" in first_markdown
    assert "## Firmware" in first_markdown
    assert "## Debug" in first_markdown
    assert "SECRET_FIRMWARE_BODY" not in first_json
    assert "SECRET_FIRMWARE_BODY" not in first_markdown
    assert "UnifiedPCBModel" not in first_json
    assert "UnifiedDatasheetModel" not in first_json


def test_aggregator_keeps_partial_failure_without_inventing_recommendations() -> None:
    report = ResultAggregator().aggregate(
        (
            AgentExecutionResult(
                agent_name="FirmwareAgent",
                status=AgentStatus.ERROR,
                result=None,
            ),
        )
    )

    assert report.firmware_section is None
    assert report.recommendations == ()
    assert report.summary.succeeded == 0
    assert report.summary.failed == 1
    assert report.summary.source_agent == "SupervisorAgent"
    assert report.summary.source_id == "supervisor:engineering-report"


def test_report_omits_absolute_firmware_paths() -> None:
    report = ResultAggregator().aggregate(
        (
            AgentExecutionResult(
                agent_name="FirmwareAgent",
                status=AgentStatus.SUCCESS,
                result=FirmwareProject(
                    name="demo",
                    platform="ESP32",
                    files=[
                        ProjectFile(
                            path="C:\\Users\\private\\main.c",
                            content="PRIVATE_SOURCE_BODY",
                            language="C",
                        )
                    ],
                ),
            ),
        )
    )

    assert report.firmware_section is not None
    assert report.firmware_section.file_paths == ()
    serialized = render_report_json(report)
    assert "Users" not in serialized
    assert "PRIVATE_SOURCE_BODY" not in serialized


def test_report_omits_sensitive_free_text_from_every_domain() -> None:
    canaries = (
        "C:\\Users\\private\\board.kicad_pcb",
        "https://private.example/evidence",
        "api_key=TOP_SECRET_VALUE",
        "Bearer PRIVATE_BEARER_TOKEN",
        "first log line\nsecond log line",
        "ghp_private_token_value",
        "mailto:private@example.com",
        "/Users/alice/private/file.pdf",
        "/workspace/private/build.log",
        "path:C:\\Users\\alice\\secret.txt",
        "access_token=TOP_SECRET_ACCESS",
        "client_secret=TOP_SECRET_CLIENT",
    )
    results = (
        AgentExecutionResult(
            agent_name="HardwareAgent",
            status=AgentStatus.SUCCESS,
            result=HardwarePlan(
                project_name="camera",
                platform="ESP32",
                mcu="ESP32-S3",
                components=[
                    HardwareComponent(
                        name=canaries[1],
                        category="camera",
                        description="Synthetic component.",
                    )
                ],
                constraints=[canaries[0]],
                rationale=canaries[3],
            ),
        ),
        AgentExecutionResult(
            agent_name="PCBAgent",
            status=AgentStatus.SUCCESS,
            result=PCBReviewReport(
                project_name="camera",
                issues=[
                    PCBIssue(
                        id="unsafe",
                        category="power",
                        severity="warning",
                        description="Safe PCB finding.",
                        evidence=[canaries[4]],
                        recommendation=canaries[2],
                    )
                ],
                summary=canaries[1],
                warnings=[canaries[0]],
            ),
        ),
        AgentExecutionResult(
            agent_name="DebugAgent",
            status=AgentStatus.SUCCESS,
            result=DebugReport(
                project_name="camera",
                platform="ESP32",
                error_type="compile_error",
                summary=canaries[0],
                findings=[
                    DebugFinding(
                        id="unsafe",
                        category="compiler",
                        severity="error",
                        description="Safe debug finding.",
                        evidence=[canaries[1]],
                        recommendation=canaries[3],
                    )
                ],
                recommendations=[
                    canaries[2],
                    canaries[4],
                    *canaries[5:],
                ],
            ),
        ),
    )

    report = ResultAggregator().aggregate(results)
    serialized = render_report_json(report) + render_report_markdown(report)

    for canary in canaries:
        assert canary not in serialized
    assert "TOP_SECRET_VALUE" not in serialized
    assert "PRIVATE_BEARER_TOKEN" not in serialized


def test_markdown_renderer_escapes_agent_supplied_markdown() -> None:
    report = ResultAggregator().aggregate(
        (
            AgentExecutionResult(
                agent_name="DebugAgent",
                status=AgentStatus.SUCCESS,
                result=DebugReport(
                    project_name="camera",
                    platform="ESP32",
                    error_type="compile_error",
                    summary="# Forged heading",
                ),
            ),
        )
    )

    markdown = render_report_markdown(report)

    assert "\\# Forged heading" in markdown
    assert "\n# Forged heading\n" not in markdown


def test_report_source_ids_resolve_to_execution_results_or_findings() -> None:
    report = ResultAggregator().aggregate(_results())
    execution_sources = {
        event.source_id
        for event in report.trace
        if event.stage == "agent_executed"
    }
    sections = tuple(
        section
        for section in (
            report.hardware_section,
            report.firmware_section,
            report.pcb_section,
            report.debug_section,
        )
        if section is not None
    )
    finding_sources = {
        finding.source_id
        for section in (report.pcb_section, report.debug_section)
        if section is not None
        for finding in section.findings
    }
    debug_recommendation_sources = {
        recommendation.source_id
        for recommendation in (
            report.debug_section.recommendations
            if report.debug_section is not None
            else ()
        )
    }

    assert {section.source_id for section in sections} <= execution_sources
    assert len(finding_sources) == sum(
        len(section.findings)
        for section in (report.pcb_section, report.debug_section)
        if section is not None
    )
    assert {item.source_id for item in report.recommendations} <= (
        finding_sources | debug_recommendation_sources
    )
    assert report.summary.source_id == report.trace[-1].source_id


def test_report_rejects_finding_source_outside_agent_execution_namespace() -> None:
    payload = copy.deepcopy(
        ResultAggregator().aggregate(_results()).model_dump(mode="python")
    )
    payload["pcb_section"]["findings"][0]["source_id"] = "invented:finding"
    for recommendation in payload["recommendations"]:
        if recommendation["source_agent"] == "PCBAgent":
            recommendation["source_id"] = "invented:finding"

    with pytest.raises(ValidationError, match="provenance"):
        EngineeringReport.model_validate(payload)
