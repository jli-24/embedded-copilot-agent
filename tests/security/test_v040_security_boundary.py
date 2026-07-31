from __future__ import annotations

import ast
import copy
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.engineering_memory.context import (
    MemoryContext,
    MemoryContextEvidence,
    MemoryDomain,
    MemoryRankingBreakdown,
    MemoryRetrievalRequest,
    MemoryTrustBasis,
)
from embedded_copilot.engineering_memory.exceptions import (
    MemoryAuditUnavailable,
    MemoryPermissionDenied,
)
from embedded_copilot.engineering_memory.models import (
    BoardProfileMemory,
    MemoryAuditEvent,
    MemoryAuditEventType,
    MemoryProvenance,
    MemorySnapshotRecord,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from embedded_copilot.engineering_memory.retrieval import (
    create_engineering_memory_retriever,
)
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.knowledge.models import KnowledgeQuery
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.context import (
    EngineeringPlanningContext,
    ExecutionContext,
    KnowledgeContext,
)
from embedded_copilot.supervisor.models import SupervisorPlan, SupervisorTask
from embedded_copilot.supervisor.planner import SupervisorPlanner
from embedded_copilot.verification_agent import VerificationSubjectType

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
FINGERPRINT_A = "sha256:" + "a" * 64
FINGERPRINT_B = "sha256:" + "b" * 64
SUPERVISOR_ROOT = Path("src/embedded_copilot/supervisor")
FORBIDDEN_METADATA_KEYS = {
    "aggregate",
    "approval",
    "approval_body",
    "audit",
    "audit_metadata",
    "context_fingerprint",
    "evidence",
    "finding",
    "finding_body",
    "fingerprint_dump",
    "memory_evidence",
    "memory_id",
    "memory_records",
    "payload",
    "raw_verification_result",
    "record_id",
    "runtime_object",
    "source_snapshot_fingerprint",
    "store_aggregate",
    "verification_result",
}


def _ranking() -> MemoryRankingBreakdown:
    return MemoryRankingBreakdown(
        verification_millis=1000,
        domain_millis=1000,
        usage_millis=0,
        recency_millis=1000,
        total_millis=800,
        relevance_score=0.8,
    )


def _memory_context() -> MemoryContext:
    ranking = _ranking()
    return MemoryContext(
        request_id="memory-request-1",
        project_id="project-1",
        memory_id="memory-1",
        aggregate_revision=1,
        domains=(MemoryDomain.FIRMWARE,),
        records=(
            MemorySnapshotRecord(
                record_id="record-1",
                memory_type=MemoryType.BOARD_PROFILE,
                logical_key="board-profile",
                payload=BoardProfileMemory(
                    board_id="board-1",
                    board_name="private board payload sentinel",
                    mcu_family="STM32",
                    mcu_model="STM32F407VG",
                    architecture="ARM Cortex-M4",
                ),
                provenance=MemoryProvenance(
                    source_type=MemorySourceType.VERIFICATION_RESULT,
                    source_reference="verification-1",
                    source_revision="revision-1",
                    created_by="reviewer-1",
                    observed_at=UTC_TIME,
                ),
                status=MemoryStatus.VERIFIED,
                record_revision=1,
            ),
        ),
        evidence=(
            MemoryContextEvidence(
                record_id="record-1",
                memory_type=MemoryType.BOARD_PROFILE,
                logical_key="board-profile",
                trust_basis=MemoryTrustBasis.VERIFICATION,
                verification_subject=VerificationSubjectType.FIRMWARE,
                verification_confidence=1.0,
                provenance_source_type=MemorySourceType.VERIFICATION_RESULT,
                provenance_reference="verification-1",
                last_transition_at=UTC_TIME,
                ranking=ranking,
            ),
        ),
        confidence=1.0,
        source_snapshot_fingerprint=FINGERPRINT_A,
        context_fingerprint=FINGERPRINT_B,
    )


def _binding() -> MemoryRetrievalRequest:
    return MemoryRetrievalRequest(
        request_id="memory-request-1",
        project_id="project-1",
        memory_id="memory-1",
        caller="SupervisorAgent",
        requested_at=UTC_TIME,
        usage_signals=(),
        limit=8,
        domains=(MemoryDomain.FIRMWARE,),
    )


def _task(metadata: dict[str, object] | None = None) -> AgentTask:
    values = {"required_agents": ["firmware"]}
    if metadata is not None:
        values.update(copy.deepcopy(metadata))
    return AgentTask(
        task_id="task-1",
        task_type="firmware",
        requirement="review firmware structure",
        metadata=values,
    )


def _knowledge_context() -> KnowledgeContext:
    return KnowledgeContext(
        query=KnowledgeQuery(query="safe knowledge query"),
        retrieved_documents=(),
        summary="No knowledge results.",
    )


class RecordingPlanner:
    def __init__(self) -> None:
        self.contexts: list[EngineeringPlanningContext] = []
        self.context_calls = 0
        self.legacy_calls = 0
        self._delegate = SupervisorPlanner()

    def plan(self, task: SupervisorTask) -> SupervisorPlan:
        self.legacy_calls += 1
        return self._delegate.plan(task)

    def plan_with_context(
        self,
        task: SupervisorTask,
        context: EngineeringPlanningContext,
    ) -> SupervisorPlan:
        self.context_calls += 1
        self.contexts.append(context)
        return self._delegate.plan(task)


class RecordingAgent(BaseAgent):
    name = "FirmwareAgent"
    description = "v0.40 security boundary fake"
    capabilities = ("firmware",)

    def __init__(self) -> None:
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=FirmwareProject(
                name="security_boundary",
                platform="STM32",
            ).model_dump_json(),
        )


class ContextRetriever:
    def __init__(self, context: MemoryContext) -> None:
        self.context = context
        self.calls = 0

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryContext:
        self.calls += 1
        return self.context


class FailingMemoryPort:
    def __init__(self, failure: Exception, *, cause: Exception | None = None) -> None:
        self.failure = failure
        self.cause = cause
        self.calls = 0

    def execute(self, request: object) -> object:
        self.calls += 1
        if self.cause is None:
            raise self.failure
        raise self.failure from self.cause


def _supervisor(
    *,
    planner: RecordingPlanner,
    agent: RecordingAgent,
    retriever: object | None = None,
    binding: MemoryRetrievalRequest | None = None,
) -> SupervisorAgent:
    return SupervisorAgent(
        planner=planner,  # type: ignore[arg-type]
        agents=(agent,),
        memory_retriever=retriever,  # type: ignore[arg-type]
        memory_binding=binding,
    )


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_supervisor_imports_only_read_side_memory_boundaries() -> None:
    agent_path = Path(inspect.getsourcefile(SupervisorAgent) or "")
    imports = _imports(agent_path)
    forbidden_modules = (
        "embedded_copilot.engineering_memory.audit",
        "embedded_copilot.engineering_memory.factory",
        "embedded_copilot.engineering_memory.ports",
        "embedded_copilot.engineering_memory.service",
        "embedded_copilot.engineering_memory.stores",
    )
    assert all(
        not module.startswith(forbidden)
        for module in imports
        for forbidden in forbidden_modules
    )
    source = agent_path.read_text(encoding="utf-8")
    for symbol in (
        "EngineeringMemoryAggregate",
        "EngineeringMemoryStorePort",
        "InMemoryEngineeringMemoryStore",
        "MemoryAuditSink",
        "MemoryPermissionPort",
    ):
        assert symbol not in source


def test_supervisor_has_no_database_filesystem_or_store_access() -> None:
    forbidden_modules = {"os", "pathlib", "shelve", "sqlalchemy", "sqlite3"}
    forbidden_calls = {"open", "read", "read_text", "write", "write_text"}
    for path in (SUPERVISOR_ROOT / "agent.py", SUPERVISOR_ROOT / "context.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert not forbidden_modules.intersection(
            module.split(".", 1)[0] for module in _imports(path)
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, (path, node.func.id)
            if isinstance(node, ast.Attribute):
                assert node.attr not in {
                    "_audit_sink",
                    "_permission_port",
                    "_store",
                    "read_bytes",
                    "write_bytes",
                }, (path, node.attr)


@pytest.mark.parametrize(
    "metadata",
    (
        {"payload": "private"},
        {"safe": {"finding_body": "private"}},
        {"safe": {"approval_body": "private"}},
        {"raw_verification_result": {"status": "PASS"}},
        {"store_aggregate": object()},
        {"audit_metadata": {"adapter": "private"}},
        {"runtime_object": object()},
        {"context_fingerprint": FINGERPRINT_A},
    ),
)
def test_execution_context_rejects_sensitive_metadata(
    metadata: dict[str, object],
) -> None:
    task = _task(metadata)
    with pytest.raises(ValidationError):
        ExecutionContext(
            task=task,
            knowledge_context=_knowledge_context(),
            execution_id=uuid4(),
        )


def test_caller_metadata_is_projected_before_agent_handoff() -> None:
    task = _task(
        {
            "safe_marker": "preserved",
            "memory_records": [{"record_id": "record-secret"}],
            "nested": {
                "safe_value": "preserved-nested",
                "payload": "private payload sentinel",
                "finding": "private finding sentinel",
                "approval_body": "private approval sentinel",
                "fingerprint_dump": FINGERPRINT_A,
            },
        }
    )
    before = copy.deepcopy(task.model_dump(mode="python"))
    planner = RecordingPlanner()
    agent = RecordingAgent()

    result = _supervisor(planner=planner, agent=agent).run(task)

    assert result.status is AgentStatus.SUCCESS
    assert task.model_dump(mode="python") == before
    assert len(agent.tasks) == 1
    metadata = agent.tasks[0].metadata
    assert metadata["safe_marker"] == "preserved"
    assert metadata["nested"] == {"safe_value": "preserved-nested"}
    serialized = json.dumps(metadata, sort_keys=True)
    assert FORBIDDEN_METADATA_KEYS.isdisjoint(metadata)
    for sentinel in ("record-secret", "private", FINGERPRINT_A):
        assert sentinel not in serialized


def test_memory_payload_is_projected_out_of_planning_and_agent_context() -> None:
    memory = _memory_context()
    memory_before = memory.model_dump_json()
    retriever = ContextRetriever(memory)
    planner = RecordingPlanner()
    agent = RecordingAgent()

    result = _supervisor(
        planner=planner,
        agent=agent,
        retriever=retriever,
        binding=_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert retriever.calls == planner.context_calls == 1
    assert memory.model_dump_json() == memory_before
    planning = planner.contexts[0]
    serialized = planning.model_dump_json()
    assert "private board payload sentinel" not in serialized
    assert "payload" not in serialized
    assert "BoardProfileMemory" not in serialized
    assert "record-1" not in agent.tasks[0].model_dump_json()


def test_permission_denial_is_an_opaque_empty_context_without_bypass() -> None:
    port = FailingMemoryPort(MemoryPermissionDenied())
    retriever = create_engineering_memory_retriever(memory_port=port)  # type: ignore[arg-type]
    planner = RecordingPlanner()
    agent = RecordingAgent()

    result = _supervisor(
        planner=planner,
        agent=agent,
        retriever=retriever,
        binding=_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert port.calls == 1
    assert planner.context_calls == 1
    memory = planner.contexts[0].memory_context
    assert memory is not None
    assert memory.records == memory.evidence == ()
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_succeeded",
        "memory_count": 0,
    }
    assert "fallback_trace" not in result.metadata


def test_audit_failure_is_sanitized_as_memory_fallback() -> None:
    port = FailingMemoryPort(
        MemoryAuditUnavailable(),
        cause=RuntimeError("database C:\\private\\memory.db token=secret"),
    )
    retriever = create_engineering_memory_retriever(memory_port=port)  # type: ignore[arg-type]
    planner = RecordingPlanner()
    agent = RecordingAgent()

    result = _supervisor(
        planner=planner,
        agent=agent,
        retriever=retriever,
        binding=_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert port.calls == 1
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_failed",
        "memory_count": 0,
    }
    assert result.metadata["fallback_trace"] == [
        {
            "event": "memory_failed",
            "stage": "MemoryUnavailable",
            "memory_count": 0,
        },
        {
            "event": "fallback_used",
            "stage": "MemoryUnavailable",
            "memory_count": 0,
        },
    ]
    serialized = result.model_dump_json().casefold()
    for forbidden in ("database", "private", "memory.db", "token", "secret"):
        assert forbidden not in serialized


def test_trace_and_memory_audit_contracts_are_content_bounded() -> None:
    assert set(MemoryAuditEvent.model_fields).isdisjoint(
        {
            "context",
            "evidence",
            "exception",
            "finding",
            "payload",
            "record",
            "traceback",
        }
    )
    assert MemoryAuditEventType.MEMORY_FAILED in tuple(MemoryAuditEventType)

    result = _supervisor(
        planner=RecordingPlanner(),
        agent=RecordingAgent(),
        retriever=ContextRetriever(_memory_context()),
        binding=_binding(),
    ).run(_task())
    assert all(
        set(item) == {"event", "memory_count"}
        for item in result.metadata["memory_trace"]
    )


def test_planning_context_and_nested_memory_are_frozen() -> None:
    planner = RecordingPlanner()
    result = _supervisor(
        planner=planner,
        agent=RecordingAgent(),
        retriever=ContextRetriever(_memory_context()),
        binding=_binding(),
    ).run(_task())
    assert result.status is AgentStatus.SUCCESS
    context = planner.contexts[0]
    assert context.memory_context is not None
    with pytest.raises(ValidationError):
        context.confidence = 0.0  # type: ignore[misc]
    with pytest.raises(ValidationError):
        context.memory_context.records[0].logical_key = "changed"  # type: ignore[misc]
