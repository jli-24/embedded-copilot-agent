from __future__ import annotations

from collections.abc import Callable

import pytest

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.models import PCBReviewReport
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.dispatcher import AgentDispatcher
from embedded_copilot.supervisor.models import SupervisorResult, SupervisorTask


class FakeAgent(BaseAgent):
    description = "pipeline fake"
    capabilities = ("test",)

    def __init__(
        self,
        name: str,
        result_factory: Callable[[AgentTask], AgentResult],
        *,
        mutate: bool = False,
    ) -> None:
        self.name = name
        self._result_factory = result_factory
        self._mutate = mutate
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        if self._mutate:
            task.metadata["polluted"] = True
            nested = task.metadata.get("nested")
            if isinstance(nested, dict) and isinstance(nested.get("values"), list):
                nested["values"].append("mutated")  # type: ignore[union-attr]
        return self._result_factory(task)


def _result(name: str, output: str) -> AgentResult:
    return AgentResult(
        agent_name=name,
        status=AgentStatus.SUCCESS,
        output=output,
        metadata={"verified_by": "fake"},
    )


def _agents(*, malformed_firmware: bool = False, mutate: bool = False) -> tuple[
    FakeAgent,
    FakeAgent,
    FakeAgent,
]:
    firmware_project = FirmwareProject(name="demo", platform="ESP32")
    hardware_plan = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        rationale="deterministic selection",
    )
    pcb_report = PCBReviewReport(project_name="demo", summary="review complete")
    firmware = FakeAgent(
        "FirmwareAgent",
        lambda task: _result(
            "FirmwareAgent",
            "hello sensitive body"
            if malformed_firmware
            else firmware_project.model_dump_json(),
        ),
        mutate=mutate,
    )
    hardware = FakeAgent(
        "HardwareAgent",
        lambda task: _result("HardwareAgent", hardware_plan.model_dump_json()),
    )
    pcb = FakeAgent(
        "PCBAgent",
        lambda task: _result("PCBAgent", pcb_report.model_dump_json()),
    )
    return firmware, hardware, pcb


def _task() -> AgentTask:
    return AgentTask(
        task_id="root-task",
        task_type="system_design",
        requirement="firmware code, hardware component, and PCB layout",
        metadata={
            "project_name": "demo",
            "required_agents": ["firmware", "hardware", "pcb"],
            "constraints": ["offline"],
            "nested": {"values": ["original"]},
        },
    )


def test_supervisor_pipeline_returns_complete_typed_success_report() -> None:
    firmware, hardware, pcb = _agents()
    supervisor = SupervisorAgent(agents=[firmware, hardware, pcb])

    result = supervisor.run(_task())
    report = SupervisorResult.model_validate_json(result.output)

    assert result.agent_name == "SupervisorAgent"
    assert result.status is AgentStatus.SUCCESS
    assert report.completed == ["FirmwareAgent", "HardwareAgent", "PCBAgent"]
    assert report.failed == []
    assert hardware.tasks[0].metadata["firmware_project"]["name"] == "demo"  # type: ignore[index]
    assert pcb.tasks[0].metadata["hardware_plan"]["mcu"] == "ESP32-S3"  # type: ignore[index]
    assert set(result.metadata) == {
        "supervisor_plan",
        "agent_results",
        "execution_summary",
    }
    assert result.metadata["execution_summary"] == report.model_dump(mode="json")


def test_supervisor_partial_failure_keeps_complete_report_and_continues() -> None:
    firmware, hardware, pcb = _agents(malformed_firmware=True)
    supervisor = SupervisorAgent(agents=[firmware, hardware, pcb])

    result = supervisor.run(_task())
    report = SupervisorResult.model_validate_json(result.output)

    assert result.status is AgentStatus.ERROR
    assert report.failed == ["FirmwareAgent"]
    assert report.completed == ["HardwareAgent", "PCBAgent"]
    assert "firmware_project" not in hardware.tasks[0].metadata
    assert len(hardware.tasks) == 1
    assert len(pcb.tasks) == 1
    assert report.results["FirmwareAgent"]["output"] == (  # type: ignore[index]
        "supervisor handoff validation failed"
    )
    assert "sensitive body" not in result.model_dump_json()


def test_supervisor_isolates_mutation_and_repeats_deterministically() -> None:
    firmware, hardware, pcb = _agents(mutate=True)
    supervisor = SupervisorAgent(agents=[firmware, hardware, pcb])
    task = _task()
    before = task.model_dump(mode="python")

    first = supervisor.run(task)
    second = supervisor.run(task)

    assert task.model_dump(mode="python") == before
    assert first.output == second.output
    assert first.metadata == second.metadata
    assert "polluted" not in first.model_dump_json()
    assert hardware.tasks[0].metadata["nested"] == {"values": ["original"]}
    assert hardware.tasks[1].metadata["nested"] == {"values": ["original"]}


def test_supervisor_rejects_dispatcher_and_agents_together() -> None:
    with pytest.raises(ValueError, match="cannot be provided together"):
        SupervisorAgent(dispatcher=AgentDispatcher(), agents=[])


def test_zero_argument_supervisor_registers_private_foundation_agents() -> None:
    supervisor = SupervisorAgent()

    assert supervisor._dispatcher.list_agents() == [  # noqa: SLF001
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    ]


def test_zero_argument_supervisor_runs_real_offline_typed_pipeline() -> None:
    task = AgentTask(
        task_id="real-offline",
        task_type="system_design",
        requirement=(
            "Design an ESP32 ESP-IDF camera system with firmware code, "
            "hardware components, and PCB layout"
        ),
        metadata={
            "project_name": "offline_demo",
            "required_agents": ["firmware", "hardware", "pcb"],
        },
    )

    result = SupervisorAgent().run(task)
    report = SupervisorResult.model_validate_json(result.output)

    assert result.status is AgentStatus.SUCCESS
    assert report.completed == ["FirmwareAgent", "HardwareAgent", "PCBAgent"]
    assert report.failed == []


def test_supervisor_searches_injected_knowledge_gateway_once() -> None:
    firmware, _, _ = _agents()

    class RecordingGateway:
        def __init__(self) -> None:
            self.queries: list[object] = []

        def search(self, query: object) -> list[object]:
            self.queries.append(query)
            return []

    gateway = RecordingGateway()
    supervisor = SupervisorAgent(
        agents=[firmware],
        knowledge_gateway=gateway,  # type: ignore[arg-type]
    )
    task = AgentTask(
        task_id="one",
        task_type="firmware",
        requirement="firmware code",
    )

    result = supervisor.run(task)

    assert result.status is AgentStatus.SUCCESS
    assert len(gateway.queries) == 1
    assert firmware.tasks[0].metadata["knowledge_mode"] == "supervisor_gateway"
    assert firmware.tasks[0].metadata["knowledge_documents"] == []


class RaisingAnalyzer:
    def analyze(self, request: str, *, metadata: object = None) -> SupervisorTask:
        raise RuntimeError("analysis sentinel C:\\private\\document.txt")


class RaisingPlanner:
    def plan(self, task: SupervisorTask) -> object:
        raise RuntimeError("planning sentinel C:\\private\\document.txt")


class RaisingDispatcher:
    def dispatch(self, task: AgentTask, plan: object) -> object:
        raise RuntimeError("dispatch sentinel C:\\private\\document.txt")


class RaisingAggregator:
    def aggregate(self, plan: object, results: object) -> object:
        raise RuntimeError("aggregation sentinel C:\\private\\document.txt")


@pytest.mark.parametrize(
    ("overrides", "expected_output", "expected_type"),
    [
        (
            {"analyzer": RaisingAnalyzer()},
            "supervisor requirement analysis failed",
            "SupervisorAnalysisError",
        ),
        (
            {"planner": RaisingPlanner()},
            "supervisor planning failed",
            "SupervisorPlanningError",
        ),
        (
            {"dispatcher": RaisingDispatcher()},
            "supervisor dispatch failed",
            "SupervisorDispatchError",
        ),
        (
            {"aggregator": RaisingAggregator()},
            "supervisor aggregation failed",
            "SupervisorAggregationError",
        ),
    ],
)
def test_supervisor_stage_failures_return_only_safe_categories(
    overrides: dict[str, object],
    expected_output: str,
    expected_type: str,
) -> None:
    firmware, _, _ = _agents()
    kwargs: dict[str, object] = {"agents": [firmware], **overrides}
    if "dispatcher" in overrides:
        kwargs.pop("agents")
    supervisor = SupervisorAgent(**kwargs)  # type: ignore[arg-type]
    task = AgentTask(
        task_id="one",
        task_type="firmware",
        requirement="firmware code",
    )

    result = supervisor.run(task)
    payload = result.model_dump_json()

    assert result.status is AgentStatus.ERROR
    assert result.output == expected_output
    assert set(result.metadata) == {
        "supervisor_plan",
        "agent_results",
        "execution_summary",
    }
    assert result.metadata["execution_summary"] == {
        "status": "error",
        "error_type": expected_type,
    }
    assert "sentinel" not in payload
    assert "private" not in payload
    assert "document" not in payload


def test_supervisor_rejects_non_agent_task_with_safe_analysis_failure() -> None:
    result = SupervisorAgent().run("not an AgentTask")  # type: ignore[arg-type]

    assert result.status is AgentStatus.ERROR
    assert result.output == "supervisor requirement analysis failed"
