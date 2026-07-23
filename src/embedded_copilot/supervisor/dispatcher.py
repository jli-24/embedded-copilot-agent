from __future__ import annotations

import copy
from collections.abc import Iterable

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.models import PCBReviewReport
from embedded_copilot.supervisor.exceptions import SupervisorDispatchError
from embedded_copilot.supervisor.models import SupervisorPlan


class AgentDispatcher:
    """Run a fixed Supervisor plan against an explicit local Agent set."""

    def __init__(self, agents: Iterable[BaseAgent] = ()) -> None:
        self._agents: dict[str, BaseAgent] = {}
        for agent in agents:
            self.register_agent(agent)

    def register_agent(self, agent: BaseAgent) -> None:
        try:
            if not isinstance(agent, BaseAgent):
                raise TypeError("agent must implement BaseAgent")
            name = agent.name.strip()
            if not name:
                raise ValueError("agent name must not be empty")
            if name in self._agents:
                raise ValueError(f"agent already registered: {name}")
        except (TypeError, ValueError) as exc:
            raise SupervisorDispatchError(str(exc)) from exc
        self._agents[name] = agent

    register = register_agent

    def get_agent(self, name: str) -> BaseAgent:
        try:
            return self._agents[name.strip()]
        except (AttributeError, KeyError) as exc:
            raise SupervisorDispatchError("unknown supervisor agent") from exc

    def list_agents(self) -> list[str]:
        return list(self._agents)

    def dispatch(
        self,
        parent_task: AgentTask,
        plan: SupervisorPlan,
    ) -> list[AgentResult]:
        handoffs: dict[str, dict[str, object]] = {}
        results: list[AgentResult] = []
        for invocation in plan.tasks:
            agent = self._agents.get(invocation.agent_name)
            if agent is None:
                results.append(self._safe_error(invocation.agent_name))
                continue
            metadata = copy.deepcopy(invocation.metadata)
            metadata.pop("firmware_project", None)
            metadata.pop("hardware_plan", None)
            metadata.update(copy.deepcopy(handoffs.get(invocation.agent_name, {})))
            task = AgentTask(
                task_id=f"{parent_task.task_id}:{invocation.agent_name}",
                task_type=invocation.agent_name,
                requirement=invocation.task,
                metadata=metadata,
            )
            result = self._run_agent(agent, invocation.agent_name, task)
            if result.status is AgentStatus.SUCCESS:
                result, handoff = self._validate_success(result)
                if handoff is not None:
                    target = {
                        "FirmwareAgent": "HardwareAgent",
                        "HardwareAgent": "PCBAgent",
                    }.get(result.agent_name)
                    if target is not None:
                        handoffs[target] = handoff
            results.append(result)
        return results

    @classmethod
    def _run_agent(
        cls,
        agent: BaseAgent,
        expected_name: str,
        task: AgentTask,
    ) -> AgentResult:
        try:
            result = agent.run(task)
            if not isinstance(result, AgentResult):
                raise TypeError("agent returned an invalid result")
            if result.agent_name != expected_name:
                raise ValueError("agent result name mismatch")
            return result
        except Exception:
            return cls._safe_error(expected_name)

    @classmethod
    def _validate_success(
        cls,
        result: AgentResult,
    ) -> tuple[AgentResult, dict[str, object] | None]:
        try:
            if result.agent_name == "FirmwareAgent":
                model = FirmwareProject.model_validate_json(result.output)
                return result, {
                    "firmware_project": copy.deepcopy(
                        model.model_dump(mode="json")
                    )
                }
            if result.agent_name == "HardwareAgent":
                model = HardwarePlan.model_validate_json(result.output)
                return result, {
                    "hardware_plan": copy.deepcopy(model.model_dump(mode="json"))
                }
            if result.agent_name == "PCBAgent":
                PCBReviewReport.model_validate_json(result.output)
                return result, None
            raise ValueError("unsupported handoff agent")
        except (ValidationError, ValueError):
            return cls._safe_error(
                result.agent_name,
                output="supervisor handoff validation failed",
            ), None

    @staticmethod
    def _safe_error(
        agent_name: str,
        *,
        output: str = "supervisor dispatch failed",
    ) -> AgentResult:
        return AgentResult(
            agent_name=agent_name,
            status=AgentStatus.ERROR,
            output=output,
            metadata={"error_type": SupervisorDispatchError.__name__},
        )
