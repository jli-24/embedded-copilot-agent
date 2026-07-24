from __future__ import annotations

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.integration.executor import AgentExecutor
from embedded_copilot.supervisor.dispatcher import AgentDispatcher
from embedded_copilot.supervisor.models import AgentInvocation, SupervisorPlan


class RecordingAgent(BaseAgent):
    description = "integration test Agent"
    capabilities = ("test",)

    def __init__(self, name: str, result: AgentResult) -> None:
        self.name = name
        self._result = result
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return self._result.model_copy(deep=True)


def _plan(*agents: str) -> SupervisorPlan:
    return SupervisorPlan(
        project_name="demo",
        tasks=[
            AgentInvocation(agent_name=name, task="engineering request")
            for name in agents
        ],
        rationale="test order",
    )


def _parent_task() -> AgentTask:
    return AgentTask(
        task_id="integration",
        task_type="end_to_end",
        requirement="engineering request",
    )


def test_executor_delegates_in_plan_order_and_preserves_agent_output() -> None:
    firmware_output = FirmwareProject(
        name="demo",
        platform="ESP32",
    ).model_dump_json(indent=2)
    hardware_output = HardwarePlan(
        project_name="demo",
        platform="ESP32",
        mcu="ESP32-S3",
        rationale="agent evidence",
    ).model_dump_json(indent=2)
    firmware = RecordingAgent(
        "FirmwareAgent",
        AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            output=firmware_output,
        ),
    )
    hardware = RecordingAgent(
        "HardwareAgent",
        AgentResult(
            agent_name="HardwareAgent",
            status=AgentStatus.SUCCESS,
            output=hardware_output,
        ),
    )
    executor = AgentExecutor(AgentDispatcher([firmware, hardware]))

    raw_results, execution_results = executor.execute_with_results(
        _parent_task(),
        _plan("FirmwareAgent", "HardwareAgent"),
    )

    assert [item.agent_name for item in execution_results] == [
        "FirmwareAgent",
        "HardwareAgent",
    ]
    assert raw_results[0].output == firmware_output
    assert raw_results[1].output == hardware_output
    assert execution_results[0].result is not None
    assert execution_results[0].result.kind == "firmware"
    assert execution_results[1].result is not None
    assert execution_results[1].result.kind == "hardware"
    assert len(firmware.tasks) == 1
    assert len(hardware.tasks) == 1


def test_executor_isolates_missing_agent_and_continues() -> None:
    firmware = RecordingAgent(
        "FirmwareAgent",
        AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            output=FirmwareProject(
                name="demo",
                platform="ESP32",
            ).model_dump_json(),
        ),
    )
    executor = AgentExecutor(AgentDispatcher([firmware]))

    raw_results, execution_results = executor.execute_with_results(
        _parent_task(),
        _plan("HardwareAgent", "FirmwareAgent"),
    )

    assert [item.status for item in execution_results] == [
        AgentStatus.ERROR,
        AgentStatus.SUCCESS,
    ]
    assert execution_results[0].result is None
    assert raw_results[0].output == "supervisor dispatch failed"
    assert len(firmware.tasks) == 1


def test_executor_has_no_standalone_public_execute_entrypoint() -> None:
    firmware = RecordingAgent(
        "FirmwareAgent",
        AgentResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            output=FirmwareProject(
                name="demo",
                platform="ESP32",
            ).model_dump_json(),
        ),
    )

    executor = AgentExecutor(AgentDispatcher([firmware]))

    assert not hasattr(executor, "execute")
