import pytest
from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.schemas.result import AgentResult as RuntimeAgentResult


class ExampleAgent(BaseAgent):
    name = "ExampleAgent"
    description = "Foundation test agent"
    capabilities = ("example",)

    def run(self, task: AgentTask) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=task.requirement,
        )


def test_agent_models_validate_and_strip_strings() -> None:
    task = AgentTask(task_id=" id-1 ", task_type=" example ", requirement=" run ")
    result = ExampleAgent().run(task)

    assert task.task_id == "id-1"
    assert result.output == "run"
    with pytest.raises(ValidationError):
        AgentTask(task_id="", task_type="example", requirement="run")
    with pytest.raises(ValidationError):
        AgentResult(agent_name="agent", status="unknown", output="x")
    with pytest.raises(ValidationError):
        AgentResult(agent_name="agent", status=AgentStatus.ERROR, output=" ")


def test_foundation_result_does_not_replace_runtime_result_contract() -> None:
    from embedded_copilot.agents import AgentResult as PublicFoundationResult

    assert PublicFoundationResult is AgentResult
    assert RuntimeAgentResult is not AgentResult


def test_base_agent_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


def test_agent_registry_lifecycle_and_duplicate_rejection() -> None:
    registry = AgentRegistry()
    agent = ExampleAgent()

    registry.register_agent(agent)

    assert registry.get_agent("ExampleAgent") is agent
    assert registry.list_agents() == ["ExampleAgent"]
    with pytest.raises(ValueError, match="already registered"):
        registry.register_agent(ExampleAgent())
    with pytest.raises(KeyError):
        registry.get_agent("missing")
