import pytest

from embedded_copilot.agents.types import AgentResult, AgentStatus
from embedded_copilot.supervisor.aggregator import SupervisorResultAggregator
from embedded_copilot.supervisor.exceptions import SupervisorAggregationError
from embedded_copilot.supervisor.models import AgentInvocation, SupervisorPlan


def _plan(*names: str) -> SupervisorPlan:
    return SupervisorPlan(
        project_name="demo",
        tasks=[AgentInvocation(agent_name=name, task="work") for name in names],
        rationale="fixed order",
    )


def _result(name: str, status: AgentStatus, output: str) -> AgentResult:
    return AgentResult(
        agent_name=name,
        status=status,
        output=output,
        metadata={"nested": {"keep": True}},
    )


def test_aggregator_preserves_complete_envelopes_and_partial_failure_order() -> None:
    plan = _plan("FirmwareAgent", "HardwareAgent", "PCBAgent")
    results = [
        _result("FirmwareAgent", AgentStatus.SUCCESS, "firmware body"),
        _result("HardwareAgent", AgentStatus.ERROR, "hardware failed"),
        _result("PCBAgent", AgentStatus.SUCCESS, "pcb body"),
    ]

    aggregated = SupervisorResultAggregator().aggregate(plan, results)

    assert aggregated.completed == ["FirmwareAgent", "PCBAgent"]
    assert aggregated.failed == ["HardwareAgent"]
    assert aggregated.results == {
        result.agent_name: result.model_dump(mode="json") for result in results
    }
    assert aggregated.summary == (
        "Supervisor execution completed: 2 succeeded, 1 failed."
    )
    assert aggregated.metadata == {
        "execution_mode": "sequential_deterministic",
        "planned_agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
    }


@pytest.mark.parametrize(
    "results",
    [
        [],
        [
            _result("HardwareAgent", AgentStatus.SUCCESS, "ok"),
            _result("FirmwareAgent", AgentStatus.SUCCESS, "ok"),
        ],
        [
            _result("FirmwareAgent", AgentStatus.SUCCESS, "ok"),
            _result("WrongAgent", AgentStatus.SUCCESS, "ok"),
        ],
    ],
)
def test_aggregator_rejects_count_order_or_name_mismatch(
    results: list[AgentResult],
) -> None:
    with pytest.raises(SupervisorAggregationError):
        SupervisorResultAggregator().aggregate(
            _plan("FirmwareAgent", "HardwareAgent"), results
        )


def test_aggregator_wraps_malformed_result_as_aggregation_error() -> None:
    with pytest.raises(SupervisorAggregationError):
        SupervisorResultAggregator().aggregate(
            _plan("FirmwareAgent"),
            [object()],  # type: ignore[list-item]
        )
