from __future__ import annotations

from collections.abc import Callable

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.models import SupervisorResult
from embedded_copilot.supervisor.models import SupervisorTask


class _FakeAgent(BaseAgent):
    description = "integration Supervisor fake"
    capabilities = ("test",)

    def __init__(
        self,
        name: str,
        result_factory: Callable[[AgentTask], AgentResult],
    ) -> None:
        self.name = name
        self._result_factory = result_factory
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return self._result_factory(task)


def _success(name: str, output: str) -> AgentResult:
    return AgentResult(
        agent_name=name,
        status=AgentStatus.SUCCESS,
        output=output,
        metadata={"source": "synthetic"},
    )


def _attachment(
    identifier: str,
    filename: str,
    media_type: AttachmentType,
    format_name: str,
) -> UserAttachment:
    return UserAttachment(
        id=identifier,
        filename=filename,
        media_type=media_type,
        content_type="application/octet-stream",
        size_bytes=128,
        metadata={"category": media_type.value, "format": format_name},
    )


def test_supervisor_adds_traceable_report_without_changing_legacy_output() -> None:
    firmware_body = "PRIVATE_GENERATED_SOURCE_BODY"
    firmware = _FakeAgent(
        "FirmwareAgent",
        lambda task: _success(
            "FirmwareAgent",
            FirmwareProject(
                name="demo",
                platform="ESP32",
                files=[
                    ProjectFile(
                        path="main/main.c",
                        content=firmware_body,
                        language="C",
                    )
                ],
            ).model_dump_json(),
        ),
    )
    supervisor = SupervisorAgent(agents=[firmware])
    task = AgentTask(
        task_id="integration-report",
        task_type="firmware",
        requirement="Generate firmware code.",
        metadata={"required_agents": ["firmware"]},
    )

    result = supervisor.run(task)
    legacy = SupervisorResult.model_validate_json(result.output)
    report = EngineeringReport.model_validate(result.metadata["engineering_report"])

    assert legacy.completed == ["FirmwareAgent"]
    assert report.firmware_section is not None
    assert report.firmware_section.source_agent == "FirmwareAgent"
    assert report.firmware_section.source_id == "agent-result:FirmwareAgent"
    assert firmware_body not in report.model_dump_json()
    assert [event.sequence for event in report.trace] == list(
        range(1, len(report.trace) + 1)
    )
    assert {event.stage for event in report.trace} >= {
        "input_analyzed",
        "agent_planned",
        "agent_executed",
        "report_aggregated",
    }


def test_supervisor_routes_attachment_metadata_through_integration_planner() -> None:
    firmware = _FakeAgent(
        "FirmwareAgent",
        lambda task: _success(
            "FirmwareAgent",
            FirmwareProject(name="demo", platform="ESP32").model_dump_json(),
        ),
    )
    debug = _FakeAgent(
        "DebugAgent",
        lambda task: _success(
            "DebugAgent",
            DebugReport(
                project_name="demo",
                platform="ESP32",
                error_type="compile_error",
                summary="Synthetic debug evidence.",
            ).model_dump_json(),
        ),
    )
    task = attach_input_context(
        AgentTask(
            task_id="metadata-routing",
            task_type="end_to_end",
            requirement="Review the supplied engineering files.",
        ),
        UnifiedInputContext(
            attachments=(
                _attachment(
                    "source-1",
                    "peripheral_driver.c",
                    AttachmentType.SOURCE_CODE,
                    "c",
                ),
                _attachment(
                    "log-1",
                    "failure.log",
                    AttachmentType.LOG,
                    "text",
                ),
            )
        ),
    )

    result = SupervisorAgent(agents=[firmware, debug]).run(task)
    legacy = SupervisorResult.model_validate_json(result.output)

    assert legacy.completed == ["FirmwareAgent", "DebugAgent"]
    assert len(firmware.tasks) == 1
    assert len(debug.tasks) == 1


def test_required_agents_override_remains_exact_with_attachment_signals() -> None:
    firmware = _FakeAgent(
        "FirmwareAgent",
        lambda task: _success(
            "FirmwareAgent",
            FirmwareProject(name="demo", platform="ESP32").model_dump_json(),
        ),
    )
    task = attach_input_context(
        AgentTask(
            task_id="exact-override",
            task_type="end_to_end",
            requirement="Review firmware, PCB, and debug files.",
            metadata={"required_agents": ["firmware"]},
        ),
        UnifiedInputContext(
            attachments=(
                _attachment(
                    "pcb-1",
                    "routing.kicad_pcb",
                    AttachmentType.EDA,
                    "kicad_pcb",
                ),
            )
        ),
    )

    result = SupervisorAgent(agents=[firmware]).run(task)
    legacy = SupervisorResult.model_validate_json(result.output)

    assert legacy.completed == ["FirmwareAgent"]


class _HardwareOnlyAnalyzer:
    def analyze(self, request: str, *, metadata: object = None) -> SupervisorTask:
        return SupervisorTask(
            request=request,
            required_agents=["HardwareAgent"],
        )


def test_supervisor_preserves_injected_analyzer_selection_without_override() -> None:
    hardware = _FakeAgent(
        "HardwareAgent",
        lambda task: _success(
            "HardwareAgent",
            HardwarePlan(
                project_name="demo",
                platform="ESP32",
                mcu="ESP32-S3",
                rationale="Validated hardware evidence.",
            ).model_dump_json(),
        ),
    )

    result = SupervisorAgent(
        analyzer=_HardwareOnlyAnalyzer(),  # type: ignore[arg-type]
        agents=[hardware],
    ).run(
        AgentTask(
            task_id="custom-analyzer",
            task_type="end_to_end",
            requirement="Generate firmware code for the device.",
        )
    )
    legacy = SupervisorResult.model_validate_json(result.output)

    assert legacy.completed == ["HardwareAgent"]
    assert legacy.failed == []
