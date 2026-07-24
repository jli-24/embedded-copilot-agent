from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.context import (
    ExecutionContext,
    KnowledgeContext,
    SupervisorTraceEvent,
)
from embedded_copilot.supervisor.models import SupervisorTask


def _knowledge_context() -> KnowledgeContext:
    return KnowledgeContext(
        query=KnowledgeQuery(
            query="ESP32 Camera",
            metadata={"domains": ["hardware"]},
        ),
        retrieved_documents=(
            KnowledgeResult(
                id="camera-reference",
                title="Camera reference",
                content="Synthetic camera guidance",
                source=KnowledgeSource.LOCAL,
                metadata={"category": "camera"},
            ),
        ),
        summary="Retrieved 1 knowledge result.",
    )


def test_knowledge_context_is_frozen_typed_and_deeply_isolated() -> None:
    query_metadata = {"domains": ["hardware"]}
    result_metadata = {"category": "camera", "nested": {"values": ["one"]}}
    context = KnowledgeContext(
        query=KnowledgeQuery(query="ESP32 Camera", metadata=query_metadata),
        retrieved_documents=(
            KnowledgeResult(
                id="camera-reference",
                title="Camera reference",
                content="Synthetic camera guidance",
                source=KnowledgeSource.LOCAL,
                metadata=result_metadata,
            ),
        ),
        summary="Retrieved 1 knowledge result.",
    )
    query_metadata["domains"].append("pcb")
    result_metadata["nested"]["values"].append("two")  # type: ignore[index]

    assert context.query.metadata == {"domains": ["hardware"]}
    assert context.retrieved_documents[0].metadata == {
        "category": "camera",
        "nested": {"values": ["one"]},
    }
    with pytest.raises(ValidationError):
        context.summary = "changed"
    with pytest.raises(ValidationError):
        KnowledgeContext(
            query=KnowledgeQuery(query="ESP32"),
            summary="empty",
            unexpected=True,
        )


def test_execution_context_keeps_uuid_internal_state_and_typed_trace() -> None:
    execution_id = uuid4()
    task = AgentTask(
        task_id="task-1",
        task_type="system_design",
        requirement="Design ESP32 camera",
        metadata={"nested": {"values": ["one"]}},
    )
    context = ExecutionContext(
        task=task,
        knowledge_context=_knowledge_context(),
        trace=(
            SupervisorTraceEvent(
                stage="task_parsed",
                status="success",
                target="SupervisorAgent",
                domains=("hardware",),
                count=1,
            ),
        ),
        execution_id=execution_id,
    )
    task.metadata["nested"]["values"].append("polluted")  # type: ignore[index]

    assert isinstance(context.execution_id, UUID)
    assert context.execution_id == execution_id
    assert context.task.metadata == {"nested": {"values": ["one"]}}
    assert context.trace[0].model_dump() == {
        "stage": "task_parsed",
        "status": "success",
        "target": "SupervisorAgent",
        "domains": ("hardware",),
        "count": 1,
    }


def test_trace_event_rejects_fields_outside_safe_allowlist() -> None:
    with pytest.raises(ValidationError):
        SupervisorTraceEvent(
            stage="gateway_retrieved",
            status="error",
            target="KnowledgeGateway",
            domains=(),
            count=0,
            query="private raw query",
        )


def test_planning_context_filters_unsafe_knowledge_categories() -> None:
    context = ExecutionContext(
        task=AgentTask(
            task_id="planning-context",
            task_type="firmware",
            requirement="ESP32 firmware",
        ),
        knowledge_context=KnowledgeContext(
            query=KnowledgeQuery(
                query="ESP32 firmware",
                metadata={"domains": ["firmware"]},
            ),
            retrieved_documents=(
                KnowledgeResult(
                    id="safe-id",
                    title="Safe title",
                    content="Synthetic body",
                    source=KnowledgeSource.LOCAL,
                    metadata={
                        "category": "https://example.test/doc?token=private"
                    },
                ),
            ),
            summary="Retrieved 1 knowledge result.",
        ),
        execution_id=uuid4(),
    )
    analyzed = SupervisorTask(
        request="ESP32 firmware",
        required_agents=["FirmwareAgent"],
    )

    planning_task = SupervisorAgent._planning_task(analyzed, context)

    assert planning_task.metadata["_supervisor_knowledge"] == {
        "domains": ["firmware"],
        "result_count": 1,
        "categories": [],
        "has_results": True,
    }
