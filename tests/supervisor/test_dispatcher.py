from __future__ import annotations

import copy

import pytest

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.models import PCBReviewReport
from embedded_copilot.supervisor.dispatcher import AgentDispatcher
from embedded_copilot.supervisor.exceptions import SupervisorDispatchError
from embedded_copilot.supervisor.models import AgentInvocation, SupervisorPlan


class RecordingAgent(BaseAgent):
    description = "test double"
    capabilities = ("test",)

    def __init__(
        self,
        name: str,
        result: AgentResult | object,
        *,
        error: Exception | None = None,
        mutate_input: bool = False,
    ) -> None:
        self.name = name
        self.result = result
        self.error = error
        self.mutate_input = mutate_input
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        if self.mutate_input:
            task.metadata["polluted"] = True
            nested = task.metadata.get("nested")
            if isinstance(nested, dict):
                values = nested.get("values")
                if isinstance(values, list):
                    values.append("mutated")
        if self.error is not None:
            raise self.error
        return self.result  # type: ignore[return-value]


def _plan(*names: str, metadata: dict[str, object] | None = None) -> SupervisorPlan:
    return SupervisorPlan(
        project_name="demo",
        tasks=[
            AgentInvocation(
                agent_name=name,
                task="original full request",
                metadata=copy.deepcopy(metadata or {}),
            )
            for name in names
        ],
        rationale="deterministic test plan",
    )


def _parent_task() -> AgentTask:
    return AgentTask(
        task_id="parent-1",
        task_type="supervisor",
        requirement="original full request",
        metadata={"nested": {"values": ["original"]}},
    )


def _success(agent_name: str, output: str) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        status=AgentStatus.SUCCESS,
        output=output,
        metadata={"source": agent_name},
    )


def test_dispatcher_rejects_duplicate_registration_before_write() -> None:
    first = RecordingAgent("FirmwareAgent", _success("FirmwareAgent", "{}"))
    duplicate = RecordingAgent("FirmwareAgent", _success("FirmwareAgent", "{}"))
    dispatcher = AgentDispatcher([first])

    with pytest.raises(SupervisorDispatchError, match="already registered"):
        dispatcher.register_agent(duplicate)

    assert dispatcher.list_agents() == ["FirmwareAgent"]
    assert dispatcher.get_agent("FirmwareAgent") is first


def test_dispatcher_converts_unknown_exception_malformed_and_name_mismatch() -> None:
    exploding = RecordingAgent(
        "HardwareAgent",
        object(),
        error=RuntimeError("secret sentinel C:\\private\\payload.txt"),
    )
    malformed = RecordingAgent("PCBAgent", object())
    mismatch = RecordingAgent(
        "FirmwareAgent",
        _success("WrongAgent", "not exposed"),
    )
    dispatcher = AgentDispatcher([exploding, malformed, mismatch])

    cases = [
        (_plan("UnknownAgent"), "UnknownAgent"),
        (_plan("HardwareAgent"), "HardwareAgent"),
        (_plan("PCBAgent"), "PCBAgent"),
        (_plan("FirmwareAgent"), "FirmwareAgent"),
    ]
    for plan, expected_name in cases:
        result = dispatcher.dispatch(_parent_task(), plan)[0]
        payload = result.model_dump_json()
        assert result.agent_name == expected_name
        assert result.status is AgentStatus.ERROR
        assert result.output == "supervisor dispatch failed"
        assert result.metadata == {"error_type": "SupervisorDispatchError"}
        assert "sentinel" not in payload
        assert "private" not in payload
        assert "not exposed" not in payload


def test_dispatcher_performs_typed_handoffs_with_independent_payloads() -> None:
    firmware_project = FirmwareProject(name="demo", platform="ESP32")
    hardware_plan = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        rationale="deterministic selection",
    )
    pcb_report = PCBReviewReport(project_name="demo", summary="review complete")
    firmware = RecordingAgent(
        "FirmwareAgent",
        _success("FirmwareAgent", firmware_project.model_dump_json()),
    )
    hardware = RecordingAgent(
        "HardwareAgent",
        _success("HardwareAgent", hardware_plan.model_dump_json()),
    )
    pcb = RecordingAgent(
        "PCBAgent",
        _success("PCBAgent", pcb_report.model_dump_json()),
    )
    dispatcher = AgentDispatcher([firmware, hardware, pcb])

    results = dispatcher.dispatch(
        _parent_task(),
        _plan(
            "FirmwareAgent",
            "HardwareAgent",
            "PCBAgent",
            metadata={
                "firmware_project": {"forged": True},
                "hardware_plan": {"stale": True},
            },
        ),
    )

    assert [result.status for result in results] == [
        AgentStatus.SUCCESS,
        AgentStatus.SUCCESS,
        AgentStatus.SUCCESS,
    ]
    assert hardware.tasks[0].metadata["firmware_project"] == (
        firmware_project.model_dump(mode="json")
    )
    assert "hardware_plan" not in hardware.tasks[0].metadata
    assert pcb.tasks[0].metadata["hardware_plan"] == hardware_plan.model_dump(
        mode="json"
    )
    assert "firmware_project" not in pcb.tasks[0].metadata
    assert hardware.tasks[0].metadata["firmware_project"] is not (
        firmware_project.metadata
    )


def test_invalid_success_becomes_safe_failure_without_polluting_later_agents() -> None:
    firmware = RecordingAgent(
        "FirmwareAgent",
        _success("FirmwareAgent", "hello secret firmware body"),
    )
    hardware_plan = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        rationale="fallback from original request",
    )
    hardware = RecordingAgent(
        "HardwareAgent",
        _success("HardwareAgent", hardware_plan.model_dump_json()),
    )
    pcb_report = PCBReviewReport(project_name="demo", summary="review complete")
    pcb = RecordingAgent(
        "PCBAgent",
        _success("PCBAgent", pcb_report.model_dump_json()),
    )
    dispatcher = AgentDispatcher([firmware, hardware, pcb])

    results = dispatcher.dispatch(
        _parent_task(),
        _plan(
            "FirmwareAgent",
            "HardwareAgent",
            "PCBAgent",
            metadata={
                "firmware_project": {"forged": True},
                "hardware_plan": {"stale": True},
            },
        ),
    )

    assert results[0].status is AgentStatus.ERROR
    assert results[0].output == "supervisor handoff validation failed"
    assert results[0].metadata == {"error_type": "SupervisorDispatchError"}
    assert results[1].status is AgentStatus.SUCCESS
    assert results[2].status is AgentStatus.SUCCESS
    assert "firmware_project" not in hardware.tasks[0].metadata
    assert hardware.tasks[0].metadata.get("hardware_plan") is None
    assert "secret firmware body" not in hardware.tasks[0].model_dump_json()
    assert pcb.tasks[0].metadata["hardware_plan"] == hardware_plan.model_dump(
        mode="json"
    )


def test_dispatcher_isolates_agent_input_mutation_from_all_shared_state() -> None:
    firmware_project = FirmwareProject(name="demo", platform="ESP32")
    firmware = RecordingAgent(
        "FirmwareAgent",
        _success("FirmwareAgent", firmware_project.model_dump_json()),
        mutate_input=True,
    )
    hardware_plan = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        rationale="deterministic selection",
    )
    hardware = RecordingAgent(
        "HardwareAgent",
        _success("HardwareAgent", hardware_plan.model_dump_json()),
    )
    parent = _parent_task()
    plan = _plan(
        "FirmwareAgent",
        "HardwareAgent",
        metadata={"nested": {"values": ["plan"]}},
    )
    parent_before = parent.model_dump(mode="python")
    plan_before = plan.model_dump(mode="python")

    AgentDispatcher([firmware, hardware]).dispatch(parent, plan)

    assert parent.model_dump(mode="python") == parent_before
    assert plan.model_dump(mode="python") == plan_before
    assert "polluted" not in hardware.tasks[0].metadata
    assert hardware.tasks[0].metadata["nested"] == {"values": ["plan"]}
    assert firmware.tasks[0].task_id == "parent-1:FirmwareAgent"
    assert hardware.tasks[0].task_id == "parent-1:HardwareAgent"


def test_dispatcher_does_not_modify_valid_original_agent_result() -> None:
    report = PCBReviewReport(project_name="demo", summary="review complete")
    original = _success("PCBAgent", report.model_dump_json())
    agent = RecordingAgent("PCBAgent", original)

    returned = AgentDispatcher([agent]).dispatch(
        _parent_task(), _plan("PCBAgent")
    )[0]

    assert returned is original
    assert returned.model_dump(mode="python") == original.model_dump(mode="python")
