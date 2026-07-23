from __future__ import annotations

import copy
from collections.abc import Sequence

from embedded_copilot.agents.types import AgentResult, AgentStatus
from embedded_copilot.supervisor.exceptions import SupervisorAggregationError
from embedded_copilot.supervisor.models import SupervisorPlan, SupervisorResult


class SupervisorResultAggregator:
    """Validate and aggregate fixed-order domain Agent results."""

    def aggregate(
        self,
        plan: SupervisorPlan,
        results: Sequence[AgentResult],
    ) -> SupervisorResult:
        if not isinstance(plan, SupervisorPlan) or any(
            not isinstance(result, AgentResult) for result in results
        ):
            raise SupervisorAggregationError(
                "supervisor aggregation input does not match plan"
            )
        planned_agents = [task.agent_name for task in plan.tasks]
        result_agents = [result.agent_name for result in results]
        if len(results) != len(plan.tasks) or result_agents != planned_agents:
            raise SupervisorAggregationError(
                "supervisor aggregation input does not match plan"
            )
        completed = [
            result.agent_name
            for result in results
            if result.status is AgentStatus.SUCCESS
        ]
        failed = [
            result.agent_name
            for result in results
            if result.status is AgentStatus.ERROR
        ]
        if len(completed) + len(failed) != len(results):
            raise SupervisorAggregationError("supervisor result status is invalid")
        return SupervisorResult(
            project_name=plan.project_name,
            completed=completed,
            failed=failed,
            results={
                result.agent_name: copy.deepcopy(result.model_dump(mode="json"))
                for result in results
            },
            summary=(
                "Supervisor execution completed: "
                f"{len(completed)} succeeded, {len(failed)} failed."
            ),
            metadata={
                "execution_mode": "sequential_deterministic",
                "planned_agents": planned_agents,
            },
        )
