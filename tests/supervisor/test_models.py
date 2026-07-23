import pytest
from pydantic import ValidationError

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.supervisor.models import (
    AgentInvocation,
    SupervisorPlan,
    SupervisorResult,
    SupervisorTask,
)


def test_supervisor_models_strip_and_stably_deduplicate_lists() -> None:
    task = SupervisorTask(
        request="  build an ESP32 device  ",
        project_name="  sensor_node  ",
        required_agents=[" FirmwareAgent ", "firmwareagent", " HardwareAgent "],
        constraints=[" Offline ", "offline", " No hardware "],
    )

    assert task.request == "build an ESP32 device"
    assert task.project_name == "sensor_node"
    assert task.required_agents == ["FirmwareAgent", "HardwareAgent"]
    assert task.constraints == ["Offline", "No hardware"]


def test_supervisor_models_are_frozen_and_forbid_extra_fields() -> None:
    invocation = AgentInvocation(
        agent_name=" FirmwareAgent ",
        task=" generate firmware ",
    )

    assert invocation.agent_name == "FirmwareAgent"
    assert invocation.task == "generate firmware"
    with pytest.raises(ValidationError):
        invocation.agent_name = "HardwareAgent"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SupervisorTask(request="valid", unexpected=True)  # type: ignore[call-arg]


def test_plan_rejects_duplicate_agent_invocations() -> None:
    with pytest.raises(ValidationError, match="duplicate agent"):
        SupervisorPlan(
            project_name="demo",
            tasks=[
                AgentInvocation(agent_name="FirmwareAgent", task="one"),
                AgentInvocation(agent_name="firmwareagent", task="two"),
            ],
            rationale="deterministic plan",
        )


def test_supervisor_result_requires_consistent_completed_failed_and_results() -> None:
    result = SupervisorResult(
        project_name="demo",
        completed=["FirmwareAgent"],
        failed=["HardwareAgent"],
        results={
            "FirmwareAgent": {
                "agent_name": "FirmwareAgent",
                "status": AgentStatus.SUCCESS,
                "output": "ok",
                "metadata": {},
            },
            "HardwareAgent": {
                "agent_name": "HardwareAgent",
                "status": AgentStatus.ERROR,
                "output": "failed",
                "metadata": {},
            },
        },
        summary="one completed and one failed",
    )

    assert result.completed == ["FirmwareAgent"]
    assert result.failed == ["HardwareAgent"]
    with pytest.raises(ValidationError, match="must not overlap"):
        SupervisorResult(
            project_name="demo",
            completed=["FirmwareAgent"],
            failed=["firmwareagent"],
            results={"FirmwareAgent": {}},
            summary="invalid",
        )
    with pytest.raises(ValidationError, match="result keys"):
        SupervisorResult(
            project_name="demo",
            completed=["FirmwareAgent"],
            results={},
            summary="invalid",
        )
