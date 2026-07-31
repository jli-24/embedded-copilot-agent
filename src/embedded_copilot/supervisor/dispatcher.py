from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping

from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.pcb.models import PCBReviewReport
from embedded_copilot.supervisor.context import ExecutionContext
from embedded_copilot.supervisor.exceptions import SupervisorDispatchError
from embedded_copilot.supervisor.knowledge_adapters import (
    adapt_debug_evidence,
    adapt_firmware_documents,
    adapt_hardware_documents,
    adapt_pcb_documents,
    knowledge_provenance,
)
from embedded_copilot.supervisor.models import SupervisorPlan


_SENSITIVE_AGENT_RESULT_METADATA_FRAGMENTS = (
    "approval",
    "audit",
    "evidence",
    "exception",
    "finding",
    "fingerprint",
    "memory",
    "payload",
    "permission",
    "provider",
    "ranking",
    "record_id",
    "traceback",
    "verification",
)
_OMIT_AGENT_RESULT_METADATA = object()


def _normalized_metadata_key(value: object) -> str | None:
    if type(value) is not str:
        return None
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _is_sensitive_metadata_key(value: object) -> bool:
    normalized = _normalized_metadata_key(value)
    return normalized is None or any(
        fragment in normalized
        for fragment in _SENSITIVE_AGENT_RESULT_METADATA_FRAGMENTS
    )


def _contains_sensitive_metadata(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            _is_sensitive_metadata_key(key) or _contains_sensitive_metadata(item)
            for key, item in value.items()
        )
    if type(value) in (list, tuple):
        return any(_contains_sensitive_metadata(item) for item in value)
    return type(value) not in (bool, float, int, str, type(None))


def _project_safe_metadata_value(value: object) -> object:
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for key, item in value.items():
            normalized = _normalized_metadata_key(key)
            if normalized is None or _is_sensitive_metadata_key(normalized):
                continue
            checked = _project_safe_metadata_value(item)
            if checked is not _OMIT_AGENT_RESULT_METADATA:
                projected[key] = checked
        return projected
    if type(value) is list:
        return [
            checked
            for item in value
            if (checked := _project_safe_metadata_value(item))
            is not _OMIT_AGENT_RESULT_METADATA
        ]
    if type(value) is tuple:
        return tuple(
            checked
            for item in value
            if (checked := _project_safe_metadata_value(item))
            is not _OMIT_AGENT_RESULT_METADATA
        )
    if type(value) in (bool, float, int, str, type(None)):
        return copy.deepcopy(value)
    return _OMIT_AGENT_RESULT_METADATA


def _sanitize_agent_result(result: AgentResult) -> AgentResult:
    if not _contains_sensitive_metadata(result.metadata):
        return result
    checked = _project_safe_metadata_value(result.metadata)
    projected = checked if isinstance(checked, dict) else {}
    payload = result.model_dump(mode="python")
    payload["metadata"] = projected
    return AgentResult.model_validate(payload)


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
        return self._dispatch(parent_task, plan, execution_context=None)

    def _dispatch_with_context(
        self,
        parent_task: AgentTask,
        plan: SupervisorPlan,
        execution_context: ExecutionContext,
    ) -> list[AgentResult]:
        if not isinstance(execution_context, ExecutionContext):
            raise SupervisorDispatchError("execution context is invalid")
        isolated = ExecutionContext.model_validate(
            copy.deepcopy(execution_context.model_dump(mode="python"))
        )
        return self._dispatch(parent_task, plan, execution_context=isolated)

    def _dispatch(
        self,
        parent_task: AgentTask,
        plan: SupervisorPlan,
        *,
        execution_context: ExecutionContext | None,
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
            if execution_context is not None:
                metadata.update(
                    self._knowledge_metadata(
                        invocation.agent_name,
                        execution_context,
                    )
                )
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

    @staticmethod
    def _knowledge_metadata(
        agent_name: str,
        execution_context: ExecutionContext,
    ) -> dict[str, object]:
        results = execution_context.knowledge_context.retrieved_documents
        domains = {
            "FirmwareAgent": "firmware",
            "HardwareAgent": "hardware",
            "PCBAgent": "pcb",
            "DebugAgent": "debug",
        }
        domain = domains.get(agent_name)
        if domain is None:
            raise SupervisorDispatchError("unsupported contextual agent")
        metadata: dict[str, object] = {
            "knowledge_mode": "supervisor_gateway",
            "knowledge_provenance": knowledge_provenance(
                results,
                domain=domain,
            ),
        }
        if agent_name == "FirmwareAgent":
            metadata["knowledge_documents"] = [
                item.model_dump(mode="json")
                for item in adapt_firmware_documents(results)
            ]
        elif agent_name == "HardwareAgent":
            metadata["knowledge_documents"] = [
                item.model_dump(mode="json")
                for item in adapt_hardware_documents(results)
            ]
        elif agent_name == "PCBAgent":
            metadata["knowledge_documents"] = [
                item.model_dump(mode="json") for item in adapt_pcb_documents(results)
            ]
        else:
            metadata["knowledge_evidence"] = [
                item.model_dump(mode="json") for item in adapt_debug_evidence(results)
            ]
        return metadata

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
            return _sanitize_agent_result(result)
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
            if result.agent_name == "DebugAgent":
                DebugReport.model_validate_json(result.output)
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
