from __future__ import annotations

import ast
import copy
import inspect
from datetime import UTC, datetime

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
from embedded_copilot.engineering_memory.models import (
    BoardProfileMemory,
    MemoryProvenance,
    MemorySnapshotRecord,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
)
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.input.adapters.supervisor import attach_input_context
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.analyzer import SupervisorRequirementAnalyzer
from embedded_copilot.supervisor.context import (
    EngineeringPlanningContext,
    SupervisorMemoryTraceEvent,
)
from embedded_copilot.supervisor.models import SupervisorPlan, SupervisorTask
from embedded_copilot.supervisor.planner import SupervisorPlanner
from embedded_copilot.verification_agent import VerificationSubjectType

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=UTC)
FINGERPRINT_A = "sha256:" + "a" * 64
FINGERPRINT_B = "sha256:" + "b" * 64


def _ranking() -> MemoryRankingBreakdown:
    return MemoryRankingBreakdown(
        verification_millis=1000,
        domain_millis=1000,
        usage_millis=0,
        recency_millis=1000,
        total_millis=800,
        relevance_score=0.8,
    )


def _memory_context(*, empty: bool = False) -> MemoryContext:
    if empty:
        return MemoryContext(
            request_id="memory-request-1",
            project_id="project-1",
            memory_id="memory-1",
            aggregate_revision=0,
            domains=(MemoryDomain.FIRMWARE,),
            records=(),
            evidence=(),
            confidence=0.0,
            source_snapshot_fingerprint=FINGERPRINT_A,
            context_fingerprint=FINGERPRINT_B,
        )
    ranking = _ranking()
    record = MemorySnapshotRecord(
        record_id="record-1",
        memory_type=MemoryType.BOARD_PROFILE,
        logical_key="board-profile",
        payload=BoardProfileMemory(
            board_id="board-1",
            board_name="private memory payload sentinel",
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
    )
    evidence = MemoryContextEvidence(
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
    )
    return MemoryContext(
        request_id="memory-request-1",
        project_id="project-1",
        memory_id="memory-1",
        aggregate_revision=1,
        domains=(MemoryDomain.FIRMWARE,),
        records=(record,),
        evidence=(evidence,),
        confidence=1.0,
        source_snapshot_fingerprint=FINGERPRINT_A,
        context_fingerprint=FINGERPRINT_B,
    )


def _memory_binding() -> MemoryRetrievalRequest:
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


class RecordingRetriever:
    def __init__(
        self,
        result: MemoryContext | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = _memory_context() if result is None else result
        self.error = error
        self.requests: list[MemoryRetrievalRequest] = []

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryContext:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class RecordingPlanner:
    def __init__(self, *, fail_with_context: bool = False) -> None:
        self.legacy_calls = 0
        self.contexts: list[EngineeringPlanningContext] = []
        self._delegate = SupervisorPlanner()
        self._fail_with_context = fail_with_context

    def plan(self, task: SupervisorTask) -> SupervisorPlan:
        self.legacy_calls += 1
        return self._delegate.plan(task)

    def plan_with_context(
        self,
        task: SupervisorTask,
        context: EngineeringPlanningContext,
    ) -> SupervisorPlan:
        self.contexts.append(context)
        if self._fail_with_context:
            raise RuntimeError("planning failed with private memory sentinel")
        return self._delegate.plan(task)


class RecordingKnowledgeGateway:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[KnowledgeQuery] = []

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return [
            KnowledgeResult(
                id="datasheet-1",
                title="Official datasheet",
                content="Synthetic knowledge body",
                source=KnowledgeSource.LOCAL,
                score=0.9,
                metadata={"source_type": "datasheet"},
            )
        ]


class FirmwareAgentFake(BaseAgent):
    name = "FirmwareAgent"
    description = "memory integration fake"
    capabilities = ("firmware",)

    def __init__(self) -> None:
        self.tasks: list[AgentTask] = []

    def run(self, task: AgentTask) -> AgentResult:
        self.tasks.append(task)
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=FirmwareProject(
                name="memory_integration",
                platform="STM32",
            ).model_dump_json(),
        )


class RecordingInputAnalyzer:
    def __init__(self) -> None:
        self.tasks: list[SupervisorTask] = []

    def analyze(
        self,
        requirement: str,
        *,
        metadata: object = None,
    ) -> SupervisorTask:
        analyzed = SupervisorRequirementAnalyzer().analyze(
            requirement,
            metadata=metadata,  # type: ignore[arg-type]
        )
        self.tasks.append(analyzed)
        return analyzed


def _task() -> AgentTask:
    return AgentTask(
        task_id="task-1",
        task_type="firmware",
        requirement="review firmware structure",
        metadata={"required_agents": ["firmware"]},
    )


def _supervisor(
    *,
    analyzer: RecordingInputAnalyzer | None = None,
    planner: RecordingPlanner | None = None,
    retriever: RecordingRetriever | None = None,
    binding: MemoryRetrievalRequest | None = None,
    gateway: RecordingKnowledgeGateway | None = None,
    agent: FirmwareAgentFake | None = None,
) -> tuple[SupervisorAgent, RecordingPlanner, FirmwareAgentFake]:
    active_planner = RecordingPlanner() if planner is None else planner
    active_agent = FirmwareAgentFake() if agent is None else agent
    supervisor = SupervisorAgent(
        analyzer=analyzer,  # type: ignore[arg-type]
        planner=active_planner,  # type: ignore[arg-type]
        agents=(active_agent,),
        knowledge_gateway=gateway,  # type: ignore[arg-type]
        memory_retriever=retriever,  # type: ignore[arg-type]
        memory_binding=binding,
    )
    return supervisor, active_planner, active_agent


def test_typed_input_envelope_survives_safe_supervisor_projection() -> None:
    input_context = UnifiedInputContext(text="typed supervisor context")
    task = attach_input_context(
        _task().model_copy(
            update={
                "metadata": {
                    **_task().metadata,
                    "execution_parameters": {"mode": "review"},
                    "payload": "private input payload",
                }
            }
        ),
        input_context,
    )
    task_before = copy.deepcopy(task)
    analyzer = RecordingInputAnalyzer()
    supervisor, _, agent = _supervisor(analyzer=analyzer)

    result = supervisor.run(task)

    assert result.status is AgentStatus.SUCCESS
    assert len(analyzer.tasks) == 1
    assert analyzer.tasks[0].input_context == input_context
    assert len(agent.tasks) == 1
    assert agent.tasks[0].metadata["execution_parameters"] == {"mode": "review"}
    assert "_supervisor_input_context" not in agent.tasks[0].metadata
    assert "payload" not in agent.tasks[0].metadata
    assert "_supervisor_input_context" not in result.model_dump_json()
    assert "private input payload" not in result.model_dump_json()
    assert task == task_before


def test_no_memory_configuration_preserves_legacy_behavior() -> None:
    supervisor, planner, _ = _supervisor()
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert planner.legacy_calls == 1
    assert planner.contexts == []
    assert set(result.metadata) == {
        "supervisor_plan",
        "agent_results",
        "execution_summary",
        "engineering_report",
    }


def test_memory_enabled_builds_planning_context_and_safe_trace() -> None:
    retriever = RecordingRetriever()
    supervisor, planner, agent = _supervisor(
        retriever=retriever,
        binding=_memory_binding(),
    )
    binding_before = _memory_binding().model_dump_json()
    result = supervisor.run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert len(retriever.requests) == 1
    assert retriever.requests[0].model_dump_json() == binding_before
    assert planner.legacy_calls == 0
    assert len(planner.contexts) == 1
    planning_context = planner.contexts[0]
    assert planning_context.memory_context is not None
    assert len(planning_context.memory_context.records) == 1
    assert planning_context.knowledge_context is None
    assert result.metadata["memory_trace"] == [
        {"event": "retrieval_attempted", "memory_count": 0},
        {"event": "retrieval_succeeded", "memory_count": 1},
    ]
    assert "memory" not in agent.tasks[0].metadata


def test_knowledge_and_memory_are_fused_for_context_aware_planner() -> None:
    gateway = RecordingKnowledgeGateway()
    supervisor, planner, _ = _supervisor(
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
        gateway=gateway,
    )
    result = supervisor.run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert len(gateway.queries) == 1
    context = planner.contexts[0]
    assert context.knowledge_context is not None
    assert context.memory_context is not None
    assert context.knowledge_context.sources[0].source_id == "datasheet-1"
    assert context.knowledge_context.sources[0].reference == "datasheet-1"
    assert context.knowledge_context.sources[0].trust_level == 0.5
    assert context.confidence == 0.5


def test_missing_retriever_falls_back_to_empty_memory_and_continues() -> None:
    supervisor, planner, _ = _supervisor(binding=_memory_binding())
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert planner.contexts[0].memory_context is None
    assert result.metadata["memory_trace"] == [
        {"event": "retrieval_attempted", "memory_count": 0},
        {"event": "retrieval_failed", "memory_count": 0},
    ]


def test_empty_memory_result_is_a_successful_fallback() -> None:
    retriever = RecordingRetriever(_memory_context(empty=True))
    supervisor, planner, _ = _supervisor(
        retriever=retriever,
        binding=_memory_binding(),
    )
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert planner.contexts[0].memory_context is not None
    assert planner.contexts[0].memory_context.records == ()
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_succeeded",
        "memory_count": 0,
    }


def test_retriever_exception_falls_back_without_retry() -> None:
    retriever = RecordingRetriever(error=RuntimeError("private payload sentinel"))
    supervisor, planner, _ = _supervisor(
        retriever=retriever,
        binding=_memory_binding(),
    )
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert len(retriever.requests) == 1
    assert planner.contexts[0].memory_context is None
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_failed",
        "memory_count": 0,
    }
    assert "sentinel" not in result.model_dump_json()


def test_knowledge_failure_falls_back_to_memory_only() -> None:
    gateway = RecordingKnowledgeGateway(error=RuntimeError("knowledge unavailable"))
    supervisor, planner, _ = _supervisor(
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
        gateway=gateway,
    )
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert planner.contexts[0].knowledge_context is None
    assert planner.contexts[0].memory_context is not None


def test_context_aware_planning_failure_keeps_memory_audit() -> None:
    planner = RecordingPlanner(fail_with_context=True)
    supervisor, _, _ = _supervisor(
        planner=planner,
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
    )
    result = supervisor.run(_task())
    assert result.status is AgentStatus.SUCCESS
    assert planner.legacy_calls == 1
    assert len(planner.contexts) == 1
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_succeeded",
        "memory_count": 1,
    }
    assert result.metadata["fallback_trace"] == [
        {
            "event": "fallback_used",
            "stage": "FusionUnavailable",
            "memory_count": 0,
        }
    ]
    assert "sentinel" not in result.model_dump_json()


def test_supervisor_does_not_import_memory_store_or_aggregate_implementations() -> None:
    tree = ast.parse(inspect.getsource(inspect.getmodule(SupervisorAgent)))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {
        "EngineeringMemoryStorePort",
        "InMemoryEngineeringMemoryStore",
        "EngineeringMemoryAggregate",
    }
    assert forbidden.isdisjoint(imports)


def test_memory_payload_never_enters_trace_or_agent_metadata() -> None:
    supervisor, _, agent = _supervisor(
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
    )
    result = supervisor.run(_task())
    serialized = result.model_dump_json()
    assert "private memory payload sentinel" not in serialized
    assert "payload" not in serialized
    assert "record-1" not in serialized
    assert set(result.metadata["memory_trace"][0]) == {"event", "memory_count"}
    assert "memory_trace" not in agent.tasks[0].metadata


def test_memory_trace_contract_is_strict_frozen_and_content_bounded() -> None:
    event = SupervisorMemoryTraceEvent(
        event="retrieval_succeeded",
        memory_count=1,
    )
    assert tuple(SupervisorMemoryTraceEvent.model_fields) == (
        "event",
        "memory_count",
    )
    assert event.model_dump() == {
        "event": "retrieval_succeeded",
        "memory_count": 1,
    }
