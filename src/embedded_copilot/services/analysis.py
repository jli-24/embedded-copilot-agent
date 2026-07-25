from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from embedded_copilot.agents.types import AgentResult, AgentTask
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.integration.report import EngineeringReport
from embedded_copilot.services.execution import (
    ExecutionRegistry,
    ExecutionSnapshot,
)


_ALLOWED_AGENTS = frozenset({"firmware", "hardware", "pcb", "debug"})


class SupervisorWorkflow(Protocol):
    def run(self, task: AgentTask) -> AgentResult: ...


@dataclass(frozen=True, slots=True)
class AnalysisCommand:
    request: str
    input_context: UnifiedInputContext
    required_agents: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        request = self.request.strip() if isinstance(self.request, str) else ""
        if not request or len(request) > 20_000:
            raise ValueError("analysis request is invalid")
        context = UnifiedInputContext.model_validate(
            copy.deepcopy(self.input_context.model_dump(mode="python"))
        )
        agents = tuple(self.required_agents)
        if len(agents) != len(set(agents)) or any(
            agent not in _ALLOWED_AGENTS for agent in agents
        ):
            raise ValueError("required agents are invalid")
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "input_context", context)
        object.__setattr__(self, "required_agents", agents)


@dataclass(frozen=True, slots=True)
class _PendingExecution:
    execution_id: str
    command: AnalysisCommand


class AnalysisService:
    """The only bridge between the product API and Supervisor workflow."""

    def __init__(
        self,
        *,
        supervisor: SupervisorWorkflow,
        registry: ExecutionRegistry | None = None,
        timeout_seconds: float = 120.0,
        execution_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("analysis timeout is invalid")
        self._supervisor = supervisor
        self._registry = registry or ExecutionRegistry()
        self._timeout_seconds = timeout_seconds
        self._execution_id_factory = execution_id_factory or (
            lambda: str(uuid4())
        )
        self._queue: asyncio.Queue[_PendingExecution] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run_worker())

    async def close(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is None:
            return
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    async def submit(self, command: AnalysisCommand) -> ExecutionSnapshot:
        if self._worker is None or self._worker.done():
            raise RuntimeError("analysis service is not running")
        isolated = AnalysisCommand(
            request=command.request,
            input_context=command.input_context,
            required_agents=command.required_agents,
        )
        execution_id = self._execution_id_factory()
        snapshot = self._registry.create(execution_id)
        await self._queue.put(
            _PendingExecution(execution_id=execution_id, command=isolated)
        )
        return snapshot

    def get_status(self, execution_id: str) -> ExecutionSnapshot:
        return self._registry.require(execution_id)

    def get_report(self, execution_id: str) -> EngineeringReport:
        return self._registry.report(execution_id)

    async def _run_worker(self) -> None:
        while True:
            pending = await self._queue.get()
            try:
                self._registry.mark_running(pending.execution_id)
                execution = asyncio.create_task(
                    asyncio.to_thread(
                        self._execute,
                        pending.execution_id,
                        pending.command,
                    )
                )
                try:
                    report = await asyncio.wait_for(
                        asyncio.shield(execution),
                        timeout=self._timeout_seconds,
                    )
                except TimeoutError:
                    self._registry.mark_failed(
                        pending.execution_id,
                        "Analysis execution timed out.",
                    )
                    try:
                        await execution
                    except Exception:
                        pass
                except Exception:
                    self._registry.mark_failed(
                        pending.execution_id,
                        "Analysis execution failed.",
                    )
                else:
                    self._registry.mark_completed(pending.execution_id, report)
            finally:
                self._queue.task_done()
                del pending

    def _execute(
        self,
        execution_id: str,
        command: AnalysisCommand,
    ) -> EngineeringReport:
        metadata: dict[str, object] = {}
        if command.required_agents:
            metadata["required_agents"] = list(command.required_agents)
        task = attach_input_context(
            AgentTask(
                task_id=execution_id,
                task_type="end_to_end",
                requirement=command.request,
                metadata=metadata,
            ),
            command.input_context,
        )
        result = self._supervisor.run(task)
        if not isinstance(result, AgentResult):
            raise TypeError("Supervisor returned an invalid result")
        raw_report = result.metadata.get("engineering_report")
        return EngineeringReport.model_validate(copy.deepcopy(raw_report))
