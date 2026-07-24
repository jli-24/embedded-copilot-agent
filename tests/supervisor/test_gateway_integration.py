from __future__ import annotations

import copy
from collections.abc import Callable

import pytest

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.pcb.models import PCBReviewReport
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.models import SupervisorResult


class RecordingAgent(BaseAgent):
    description = "integration recorder"
    capabilities = ("test",)

    def __init__(self, name: str, output: str) -> None:
        self.name = name
        self.output = output
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=self.output,
        )


class RecordingGateway:
    def __init__(
        self,
        results: object,
        *,
        action: Callable[[KnowledgeQuery], None] | None = None,
    ) -> None:
        self.results = results
        self.action = action
        self.queries: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> object:
        self.queries.append(query)
        if self.action is not None:
            self.action(query)
        return self.results


def _agents() -> list[RecordingAgent]:
    return [
        RecordingAgent(
            "FirmwareAgent",
            FirmwareProject(name="demo", platform="ESP32").model_dump_json(),
        ),
        RecordingAgent(
            "HardwareAgent",
            HardwarePlan(
                project_name="demo",
                platform="ESP32",
                mcu="ESP32",
                rationale="synthetic",
            ).model_dump_json(),
        ),
        RecordingAgent(
            "PCBAgent",
            PCBReviewReport(
                project_name="demo",
                summary="synthetic review",
            ).model_dump_json(),
        ),
        RecordingAgent(
            "DebugAgent",
            DebugReport(
                project_name="demo",
                error_type="compile_error",
                summary="synthetic debug",
            ).model_dump_json(),
        ),
    ]


def _task() -> AgentTask:
    return AgentTask(
        task_id="gateway-integration",
        task_type="system_debug",
        requirement="Design ESP32 camera firmware and inspect a compile error",
        metadata={
            "project_name": "demo",
            "required_agents": ["firmware", "hardware", "pcb", "debug"],
            "nested": {"values": ["original"]},
        },
    )


def _knowledge() -> list[KnowledgeResult]:
    return [
        KnowledgeResult(
            id="camera-reference",
            title="Camera reference",
            content="synthetic private knowledge body",
            source=KnowledgeSource.LOCAL,
            score=0.8,
            metadata={"category": "camera"},
        )
    ]


def test_gateway_pipeline_calls_once_and_injects_minimal_domain_inputs() -> None:
    agents = _agents()
    gateway = RecordingGateway(_knowledge())
    task = _task()
    before = task.model_dump(mode="python")

    result = SupervisorAgent(
        agents=agents,
        knowledge_gateway=gateway,  # type: ignore[arg-type]
    ).run(task)
    report = SupervisorResult.model_validate_json(result.output)

    assert result.status is AgentStatus.SUCCESS
    assert task.model_dump(mode="python") == before
    assert len(gateway.queries) == 1
    assert isinstance(gateway.queries[0], KnowledgeQuery)
    assert report.completed == [
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    ]
    for agent in agents[:3]:
        metadata = agent.tasks[0].metadata
        assert metadata["knowledge_mode"] == "supervisor_gateway"
        assert len(metadata["knowledge_documents"]) == 1  # type: ignore[arg-type]
        assert set(metadata).issuperset(
            {"knowledge_mode", "knowledge_documents", "knowledge_provenance"}
        )
        assert "knowledge_evidence" not in metadata
    debug_metadata = agents[3].tasks[0].metadata
    assert debug_metadata["knowledge_mode"] == "supervisor_gateway"
    assert len(debug_metadata["knowledge_evidence"]) == 1  # type: ignore[arg-type]
    assert "knowledge_documents" not in debug_metadata
    assert "_supervisor_knowledge" not in result.model_dump_json()
    assert "synthetic private knowledge body" not in result.model_dump_json()
    assert "execution_id" not in result.model_dump_json()

    trace = report.metadata["supervisor_trace"]
    assert [event["stage"] for event in trace] == [  # type: ignore[index]
        "task_parsed",
        "knowledge_query_built",
        "gateway_retrieved",
        "context_built",
        "agent_routed",
        "agent_routed",
        "agent_routed",
        "agent_routed",
        "finished",
    ]
    assert all(
        set(event).issubset({"stage", "status", "target", "domains", "count"})
        for event in trace  # type: ignore[union-attr]
    )


@pytest.mark.parametrize(
    "results",
    [(), {"not": "a list"}, [object()]],
)
def test_gateway_contract_failures_are_safely_classified(results: object) -> None:
    agent = _agents()[0]
    result = SupervisorAgent(
        agents=[agent],
        knowledge_gateway=RecordingGateway(results),  # type: ignore[arg-type]
    ).run(
        AgentTask(
            task_id="malformed",
            task_type="firmware",
            requirement="ESP32 firmware",
            metadata={"required_agents": ["firmware"]},
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "supervisor knowledge integration failed"
    assert result.metadata["execution_summary"]["error_type"] == (  # type: ignore[index]
        "SupervisorKnowledgeError"
    )
    assert agent.tasks == []


def test_gateway_query_mutation_is_rejected_without_leaking_query() -> None:
    def mutate(query: KnowledgeQuery) -> None:
        query.metadata["domains"].append("polluted")  # type: ignore[union-attr]
        query.metadata["sentinel"] = "C:\\private\\secret.txt"

    gateway = RecordingGateway([], action=mutate)
    task = _task()
    before = copy.deepcopy(task.model_dump(mode="python"))
    result = SupervisorAgent(
        agents=_agents(),
        knowledge_gateway=gateway,  # type: ignore[arg-type]
    ).run(task)
    serialized = result.model_dump_json()

    assert task.model_dump(mode="python") == before
    assert len(gateway.queries) == 1
    assert result.status is AgentStatus.ERROR
    assert result.output == "supervisor knowledge integration failed"
    assert "polluted" not in serialized
    assert "sentinel" not in serialized
    assert "private" not in serialized
    assert "secret" not in serialized


def test_gateway_exception_is_safely_classified() -> None:
    def fail(query: KnowledgeQuery) -> None:
        raise RuntimeError("sentinel C:\\private\\secret.txt")

    result = SupervisorAgent(
        agents=[_agents()[0]],
        knowledge_gateway=RecordingGateway([], action=fail),  # type: ignore[arg-type]
    ).run(
        AgentTask(
            task_id="gateway-error",
            task_type="firmware",
            requirement="ESP32 firmware",
            metadata={"required_agents": ["firmware"]},
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "supervisor knowledge integration failed"
    assert "sentinel" not in result.model_dump_json()
    assert "private" not in result.model_dump_json()
