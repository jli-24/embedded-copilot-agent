from __future__ import annotations

import asyncio
import time

from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)
from embedded_copilot.integration.context import IntegrationTraceEvent
from embedded_copilot.integration.report import EngineeringReport, ReportSummary
from embedded_copilot.services.analysis import AnalysisCommand, AnalysisService
from embedded_copilot.services.execution import (
    ExecutionCapacityError,
    ExecutionRegistry,
    ExecutionStatus,
)


def _report() -> EngineeringReport:
    source_id = "supervisor:engineering-report"
    return EngineeringReport(
        summary=ReportSummary(
            text="Embedded Copilot execution completed: 0 succeeded, 0 failed.",
            succeeded=0,
            failed=0,
            source_agent="SupervisorAgent",
            source_id=source_id,
        ),
        trace=(
            IntegrationTraceEvent(
                sequence=1,
                stage="report_aggregated",
                status="success",
                source_agent="SupervisorAgent",
                source_id=source_id,
            ),
        ),
    )


class _Supervisor:
    def __init__(self, *, delay: float = 0.0, invalid: bool = False) -> None:
        self.delay = delay
        self.invalid = invalid
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task.model_copy(deep=True))
        if self.delay:
            time.sleep(self.delay)
        metadata = {} if self.invalid else {
            "engineering_report": _report().model_dump(mode="json")
        }
        return AgentResult(
            agent_name="SupervisorAgent",
            status=AgentStatus.SUCCESS,
            output="PRIVATE_AGENT_OUTPUT",
            metadata=metadata,
        )


class _ConcurrencySupervisor(_Supervisor):
    def __init__(self) -> None:
        super().__init__(delay=0.03)
        self.active = 0
        self.max_active = 0

    def run(self, task: AgentTask) -> AgentResult:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return super().run(task)
        finally:
            self.active -= 1


async def _wait_for(
    service: AnalysisService,
    execution_id: str,
    status: ExecutionStatus,
) -> None:
    for _ in range(100):
        if service.get_status(execution_id).status is status:
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"execution did not reach {status}")


def _command(*, required_agents: tuple[str, ...] = ()) -> AnalysisCommand:
    return AnalysisCommand(
        request="Review ESP32 camera firmware.",
        input_context=UnifiedInputContext(
            attachments=(
                UserAttachment(
                    id="source-1",
                    filename="camera.c",
                    media_type=AttachmentType.SOURCE_CODE,
                    content_type="text/x-c",
                    size_bytes=128,
                    metadata={"category": "source_code", "format": "c"},
                ),
            )
        ),
        required_agents=required_agents,
    )


def test_analysis_service_uses_supervisor_adapter_and_stores_only_report() -> None:
    async def scenario() -> None:
        supervisor = _Supervisor()
        service = AnalysisService(
            supervisor=supervisor,
            registry=ExecutionRegistry(capacity=10),
            timeout_seconds=1,
            execution_id_factory=lambda: "exec-1",
        )
        await service.start()
        try:
            snapshot = await service.submit(
                _command(required_agents=("firmware",))
            )
            assert snapshot.status is ExecutionStatus.QUEUED
            await _wait_for(service, snapshot.execution_id, ExecutionStatus.COMPLETED)
            assert len(supervisor.tasks) == 1
            task = supervisor.tasks[0]
            assert task.metadata["required_agents"] == ["firmware"]
            assert "_supervisor_input_context" in task.metadata
            assert service.get_report(snapshot.execution_id) == _report()
            stored = service.get_status(snapshot.execution_id)
            assert set(type(stored).model_fields) == {
                "execution_id",
                "status",
                "error",
            }
            assert "PRIVATE_AGENT_OUTPUT" not in stored.model_dump_json()
        finally:
            await service.close()

    asyncio.run(scenario())


def test_analysis_service_omits_empty_agent_override() -> None:
    async def scenario() -> None:
        supervisor = _Supervisor()
        service = AnalysisService(supervisor=supervisor, timeout_seconds=1)
        await service.start()
        try:
            snapshot = await service.submit(_command())
            await _wait_for(service, snapshot.execution_id, ExecutionStatus.COMPLETED)
            assert "required_agents" not in supervisor.tasks[0].metadata
        finally:
            await service.close()

    asyncio.run(scenario())


def test_analysis_service_maps_timeout_and_invalid_report_to_safe_failure() -> None:
    async def scenario() -> None:
        timeout_service = AnalysisService(
            supervisor=_Supervisor(delay=0.05),
            timeout_seconds=0.001,
        )
        invalid_service = AnalysisService(
            supervisor=_Supervisor(invalid=True),
            timeout_seconds=1,
        )
        for service in (timeout_service, invalid_service):
            await service.start()
        try:
            timed = await timeout_service.submit(_command())
            invalid = await invalid_service.submit(_command())
            await _wait_for(timeout_service, timed.execution_id, ExecutionStatus.FAILED)
            await _wait_for(invalid_service, invalid.execution_id, ExecutionStatus.FAILED)
            assert timeout_service.get_status(timed.execution_id).error == (
                "Analysis execution timed out."
            )
            assert invalid_service.get_status(invalid.execution_id).error == (
                "Analysis execution failed."
            )
        finally:
            await timeout_service.close()
            await invalid_service.close()

    asyncio.run(scenario())


def test_timed_out_supervisor_call_does_not_overlap_next_execution() -> None:
    async def scenario() -> None:
        supervisor = _ConcurrencySupervisor()
        counter = iter(("first", "second"))
        service = AnalysisService(
            supervisor=supervisor,
            timeout_seconds=0.001,
            execution_id_factory=lambda: next(counter),
        )
        await service.start()
        try:
            first = await service.submit(_command())
            second = await service.submit(_command())
            await _wait_for(service, first.execution_id, ExecutionStatus.FAILED)
            await _wait_for(service, second.execution_id, ExecutionStatus.FAILED)
            assert supervisor.max_active == 1
            assert service.get_status(first.execution_id).status is ExecutionStatus.FAILED
        finally:
            await service.close()

    asyncio.run(scenario())


def test_registry_evicts_terminal_records_but_never_active_records() -> None:
    registry = ExecutionRegistry(capacity=2)
    registry.create("first")
    registry.mark_running("first")
    registry.mark_completed("first", _report())
    registry.create("second")
    registry.create("third")

    assert registry.get("first") is None
    assert registry.get("second") is not None
    assert registry.get("third") is not None

    full = ExecutionRegistry(capacity=1)
    full.create("active")
    try:
        full.create("rejected")
    except ExecutionCapacityError:
        pass
    else:
        raise AssertionError("active execution was evicted")
