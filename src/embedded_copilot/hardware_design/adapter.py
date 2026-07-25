from __future__ import annotations

import copy

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.hardware_design.projector import project_artifact

_ENVELOPE_KEY = "_real_engineering_input"


class HardwareBlueprintProjectionAgentAdapter(BaseAgent):
    """Add an optional explanation artifact without changing Agent output."""

    def __init__(self, delegate: BaseAgent) -> None:
        self._delegate = delegate
        self.name = delegate.name
        self.description = delegate.description
        self.capabilities = delegate.capabilities

    def run(self, task: AgentTask) -> AgentResult:
        if not isinstance(task, AgentTask):
            return self._delegate.run(task)
        envelope, envelope_error = _copy_envelope(task)
        delegated = self._delegate.run(task)
        if delegated.status is AgentStatus.ERROR:
            return delegated
        if envelope_error:
            return _projection_failure(delegated)
        try:
            plan = HardwarePlan.model_validate_json(delegated.output)
            artifact = project_artifact(plan, envelope)
            metadata = copy.deepcopy(delegated.metadata)
            metadata["hardware_design"] = artifact.model_dump(mode="json")
            return delegated.model_copy(update={"metadata": metadata}, deep=True)
        except Exception:
            return _projection_failure(delegated)


def _copy_envelope(
    task: AgentTask,
) -> tuple[RealEngineeringEnvelope | None, bool]:
    raw = copy.deepcopy(task.metadata.get(_ENVELOPE_KEY))
    if raw is None:
        return None, False
    try:
        return RealEngineeringEnvelope.model_validate(raw), False
    except Exception:
        return None, True


def _projection_failure(result: AgentResult) -> AgentResult:
    metadata = copy.deepcopy(result.metadata)
    metadata["hardware_design_error"] = {"code": "projection_failed"}
    return result.model_copy(update={"metadata": metadata}, deep=True)
