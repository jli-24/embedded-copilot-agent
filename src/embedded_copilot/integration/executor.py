from __future__ import annotations

from typing import TYPE_CHECKING

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.integration.context import AgentExecutionResult
from embedded_copilot.pcb.models import PCBReviewReport

if TYPE_CHECKING:
    from embedded_copilot.supervisor.context import ExecutionContext
    from embedded_copilot.supervisor.models import SupervisorPlan


class AgentExecutor:
    """Delegate execution to the Supervisor-owned dispatcher without mutation."""

    def __init__(self, dispatcher: object) -> None:
        if not callable(getattr(dispatcher, "dispatch", None)):
            raise TypeError("integration executor requires a dispatcher")
        self._dispatcher = dispatcher

    def execute_with_results(
        self,
        parent_task: AgentTask,
        plan: SupervisorPlan,
        *,
        execution_context: ExecutionContext | None = None,
    ) -> tuple[tuple[AgentResult, ...], tuple[AgentExecutionResult, ...]]:
        from embedded_copilot.supervisor.models import SupervisorPlan

        if not isinstance(parent_task, AgentTask) or not isinstance(
            plan,
            SupervisorPlan,
        ):
            raise TypeError("integration execution input is invalid")
        if execution_context is None:
            dispatch = getattr(self._dispatcher, "dispatch", None)
            if not callable(dispatch):
                raise TypeError("integration dispatcher is invalid")
            dispatched = dispatch(parent_task, plan)
        else:
            dispatch_with_context = getattr(
                self._dispatcher,
                "_dispatch_with_context",
                None,
            )
            if not callable(dispatch_with_context):
                raise TypeError("integration dispatcher does not support context")
            dispatched = dispatch_with_context(
                parent_task,
                plan,
                execution_context,
            )
        if not isinstance(dispatched, list) or any(
            not isinstance(item, AgentResult) for item in dispatched
        ):
            raise TypeError("integration dispatcher returned invalid results")
        raw_results = tuple(dispatched)
        execution_results = tuple(self._validate_result(item) for item in raw_results)
        return raw_results, execution_results

    @staticmethod
    def _validate_result(result: AgentResult) -> AgentExecutionResult:
        if result.status is AgentStatus.ERROR:
            return AgentExecutionResult(
                agent_name=result.agent_name,
                status=result.status,
                result=None,
            )
        model_types = {
            "FirmwareAgent": FirmwareProject,
            "HardwareAgent": HardwarePlan,
            "PCBAgent": PCBReviewReport,
            "DebugAgent": DebugReport,
        }
        model_type = model_types.get(result.agent_name)
        if model_type is None:
            raise TypeError("integration Agent result is unsupported")
        return AgentExecutionResult(
            agent_name=result.agent_name,
            source_id=f"agent-result:{result.agent_name}",
            status=result.status,
            result=model_type.model_validate_json(result.output),
        )
