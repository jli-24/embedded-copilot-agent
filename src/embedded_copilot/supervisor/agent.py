from __future__ import annotations

from collections.abc import Iterable

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.knowledge.gateway import KnowledgeGateway
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.supervisor.aggregator import SupervisorResultAggregator
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.dispatcher import AgentDispatcher
from embedded_copilot.supervisor.exceptions import (
    SupervisorAggregationError,
    SupervisorAnalysisError,
    SupervisorDispatchError,
    SupervisorIntelligenceError,
    SupervisorPlanningError,
)
from embedded_copilot.supervisor.models import (
    SupervisorPlan,
    SupervisorResult,
    SupervisorTask,
)
from embedded_copilot.supervisor.planner import SupervisorPlanner


class SupervisorAgent(BaseAgent):
    """Synchronous deterministic Foundation Supervisor."""

    name = "SupervisorAgent"
    description = "Plans and orchestrates deterministic Foundation Agents."
    capabilities = (
        "task_planning",
        "agent_orchestration",
        "result_aggregation",
    )

    def __init__(
        self,
        *,
        analyzer: SupervisorRequirementAnalyzer | None = None,
        planner: SupervisorPlanner | None = None,
        dispatcher: AgentDispatcher | None = None,
        aggregator: SupervisorResultAggregator | None = None,
        agents: Iterable[BaseAgent] | None = None,
        knowledge_gateway: KnowledgeGateway | None = None,
    ) -> None:
        if dispatcher is not None and agents is not None:
            raise ValueError("dispatcher and agents cannot be provided together")
        self._analyzer = (
            analyzer if analyzer is not None else SupervisorRequirementAnalyzer()
        )
        self._planner = planner if planner is not None else SupervisorPlanner()
        if dispatcher is not None:
            self._dispatcher = dispatcher
        else:
            active_agents = (
                agents
                if agents is not None
                else (FirmwareAgent(), HardwareAgent(), PCBAgent())
            )
            self._dispatcher = AgentDispatcher(active_agents)
        self._aggregator = (
            aggregator if aggregator is not None else SupervisorResultAggregator()
        )
        self._knowledge_gateway = knowledge_gateway

    def run(self, task: AgentTask) -> AgentResult:
        plan: SupervisorPlan | None = None
        results: list[AgentResult] = []
        if not isinstance(task, AgentTask):
            return self._safe_failure(SupervisorAnalysisError, plan, results)
        try:
            analyzed = self._analyzer.analyze(
                task.requirement,
                metadata=task.model_copy(deep=True).metadata,
            )
            if not isinstance(analyzed, SupervisorTask):
                raise TypeError("analyzer returned an invalid task")
            analyzed = SupervisorTask.model_validate(
                analyzed.model_dump(mode="json")
            )
        except Exception:
            return self._safe_failure(SupervisorAnalysisError, plan, results)

        try:
            planned = self._planner.plan(analyzed.model_copy(deep=True))
            if not isinstance(planned, SupervisorPlan):
                raise TypeError("planner returned an invalid plan")
            plan = SupervisorPlan.model_validate(planned.model_dump(mode="json"))
        except Exception:
            return self._safe_failure(SupervisorPlanningError, plan, results)

        try:
            dispatched = self._dispatcher.dispatch(
                task.model_copy(deep=True),
                plan.model_copy(deep=True),
            )
            if not isinstance(dispatched, list) or any(
                not isinstance(result, AgentResult) for result in dispatched
            ):
                raise TypeError("dispatcher returned invalid results")
            results = list(dispatched)
        except Exception:
            return self._safe_failure(SupervisorDispatchError, plan, results)

        try:
            aggregated = self._aggregator.aggregate(
                plan.model_copy(deep=True),
                [result.model_copy(deep=True) for result in results],
            )
            if not isinstance(aggregated, SupervisorResult):
                raise TypeError("aggregator returned an invalid result")
            report = SupervisorResult.model_validate(
                aggregated.model_dump(mode="json")
            )
        except Exception:
            return self._safe_failure(SupervisorAggregationError, plan, results)

        return AgentResult(
            agent_name=self.name,
            status=(AgentStatus.ERROR if report.failed else AgentStatus.SUCCESS),
            output=report.model_dump_json(),
            metadata={
                "supervisor_plan": plan.model_dump(mode="json"),
                "agent_results": [
                    result.model_dump(mode="json") for result in results
                ],
                "execution_summary": report.model_dump(mode="json"),
            },
        )

    @classmethod
    def _safe_failure(
        cls,
        error_type: type[SupervisorIntelligenceError],
        plan: SupervisorPlan | None,
        results: list[AgentResult],
    ) -> AgentResult:
        messages: dict[type[SupervisorIntelligenceError], str] = {
            SupervisorAnalysisError: "supervisor requirement analysis failed",
            SupervisorPlanningError: "supervisor planning failed",
            SupervisorDispatchError: "supervisor dispatch failed",
            SupervisorAggregationError: "supervisor aggregation failed",
        }
        return AgentResult(
            agent_name=cls.name,
            status=AgentStatus.ERROR,
            output=messages[error_type],
            metadata={
                "supervisor_plan": (
                    plan.model_dump(mode="json") if plan is not None else None
                ),
                "agent_results": [
                    result.model_dump(mode="json") for result in results
                ],
                "execution_summary": {
                    "status": "error",
                    "error_type": error_type.__name__,
                },
            },
        )
