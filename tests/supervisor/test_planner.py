import pytest

from embedded_copilot.supervisor.exceptions import SupervisorPlanningError
from embedded_copilot.supervisor.models import SupervisorTask
from embedded_copilot.supervisor.planner import SupervisorPlanner


def test_planner_uses_fixed_domain_order_and_preserves_request() -> None:
    task = SupervisorTask(
        request="Original ESP32 camera system request",
        required_agents=["PCBAgent", "FirmwareAgent", "HardwareAgent"],
        constraints=["offline"],
        metadata={"trace": {"id": "abc"}},
    )

    plan = SupervisorPlanner().plan(task)

    assert plan.project_name == "supervisor_project"
    assert [item.agent_name for item in plan.tasks] == [
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
    ]
    assert all(item.task == task.request for item in plan.tasks)
    assert [item.metadata["supervisor_objective"] for item in plan.tasks] == [
        "Generate firmware architecture",
        "Create hardware design plan",
        "Review PCB constraints",
    ]
    assert plan.tasks[0].metadata["constraints"] == ["offline"]
    assert plan.metadata["execution_mode"] == "sequential_deterministic"


def test_planner_copies_nested_metadata() -> None:
    task = SupervisorTask(
        request="firmware",
        required_agents=["FirmwareAgent"],
        metadata={"nested": {"values": ["one"]}},
    )

    plan = SupervisorPlanner().plan(task)
    plan.tasks[0].metadata["nested"]["values"].append("two")  # type: ignore[index,union-attr]

    assert task.metadata == {"nested": {"values": ["one"]}}


def test_planner_rejects_empty_agent_selection() -> None:
    with pytest.raises(SupervisorPlanningError, match="requires at least one agent"):
        SupervisorPlanner().plan(SupervisorTask(request="unknown request"))


def test_planner_rejects_mixed_canonical_and_unknown_required_agents() -> None:
    task = SupervisorTask(
        request="firmware and unsupported work",
        required_agents=["FirmwareAgent", "UnknownAgent"],
    )

    with pytest.raises(SupervisorPlanningError, match="unknown agent"):
        SupervisorPlanner().plan(task)
