from __future__ import annotations

import copy

from embedded_copilot.supervisor.exceptions import SupervisorPlanningError
from embedded_copilot.supervisor.models import (
    AgentInvocation,
    SupervisorPlan,
    SupervisorTask,
)


_AGENT_ORDER = ("FirmwareAgent", "HardwareAgent", "PCBAgent", "DebugAgent")
_OBJECTIVES = {
    "FirmwareAgent": "Generate firmware architecture",
    "HardwareAgent": "Create hardware design plan",
    "PCBAgent": "Review PCB constraints",
    "DebugAgent": "Analyze observed failure evidence",
}


class SupervisorPlanner:
    """Create a fixed-order, deterministic domain Agent plan."""

    def plan(self, task: SupervisorTask) -> SupervisorPlan:
        if not isinstance(task, SupervisorTask):
            raise SupervisorPlanningError("supervisor task is invalid")
        selected = set(task.required_agents)
        unknown_agents = selected.difference(_AGENT_ORDER)
        if unknown_agents:
            raise SupervisorPlanningError(
                "supervisor plan contains an unknown agent"
            )
        ordered_agents = [name for name in _AGENT_ORDER if name in selected]
        if not ordered_agents:
            raise SupervisorPlanningError("supervisor plan requires at least one agent")

        project_name = task.project_name or "supervisor_project"
        public_metadata = copy.deepcopy(task.metadata)
        public_metadata.pop("_supervisor_knowledge", None)
        invocations: list[AgentInvocation] = []
        for agent_name in ordered_agents:
            metadata = copy.deepcopy(public_metadata)
            metadata.update(
                {
                    "project_name": project_name,
                    "constraints": copy.deepcopy(task.constraints),
                    "supervisor_objective": _OBJECTIVES[agent_name],
                }
            )
            invocations.append(
                AgentInvocation(
                    agent_name=agent_name,
                    task=task.request,
                    metadata=metadata,
                )
            )
        return SupervisorPlan(
            project_name=project_name,
            tasks=invocations,
            rationale=(
                "Rule-based agent selection with fixed sequential execution: "
                + " -> ".join(ordered_agents)
                + "."
            ),
            metadata={
                "execution_mode": "sequential_deterministic",
                "planned_agents": ordered_agents,
            },
        )
