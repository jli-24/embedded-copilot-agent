from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import embedded_copilot.supervisor.agent as supervisor_agent_module
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
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.supervisor.agent import SupervisorAgent
from embedded_copilot.supervisor.context import (
    EngineeringPlanningContext,
    SupervisorFallbackTraceEvent,
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


def _task() -> AgentTask:
    return AgentTask(
        task_id="task-1",
        task_type="firmware",
        requirement="review firmware structure",
        metadata={"required_agents": ["firmware"]},
    )


class RecordingRetriever:
    def __init__(
        self,
        *,
        result: MemoryContext | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = _memory_context() if result is None else result
        self.error = error
        self.calls = 0

    def retrieve(self, request: MemoryRetrievalRequest) -> MemoryContext:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class RecordingGateway:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        self.calls += 1
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


class RecordingPlanner:
    def __init__(self, *, context_result: str = "valid") -> None:
        self.context_result = context_result
        self.context_calls = 0
        self.legacy_calls = 0
        self.contexts: list[EngineeringPlanningContext] = []
        self._delegate = SupervisorPlanner()

    def plan(self, task: SupervisorTask) -> SupervisorPlan:
        self.legacy_calls += 1
        return self._delegate.plan(task)

    def plan_with_context(
        self,
        task: SupervisorTask,
        context: EngineeringPlanningContext,
    ) -> SupervisorPlan | object:
        self.context_calls += 1
        self.contexts.append(context)
        if self.context_result == "raise":
            raise RuntimeError("private context planning payload sentinel")
        if self.context_result == "invalid":
            return object()
        return self._delegate.plan(task)


class LegacyOnlyPlanner:
    def __init__(self) -> None:
        self.legacy_calls = 0
        self._delegate = SupervisorPlanner()

    def plan(self, task: SupervisorTask) -> SupervisorPlan:
        self.legacy_calls += 1
        return self._delegate.plan(task)


class FirmwareAgentFake(BaseAgent):
    name = "FirmwareAgent"
    description = "failure fallback fake"
    capabilities = ("firmware",)

    def __init__(self) -> None:
        self.calls = 0

    def run(self, task: AgentTask) -> AgentResult:
        self.calls += 1
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=FirmwareProject(
                name="failure_fallback",
                platform="STM32",
            ).model_dump_json(),
        )


def _supervisor(
    *,
    planner: object,
    retriever: RecordingRetriever | None = None,
    gateway: RecordingGateway | None = None,
    binding: MemoryRetrievalRequest | None = None,
    agent: FirmwareAgentFake | None = None,
) -> SupervisorAgent:
    return SupervisorAgent(
        planner=planner,  # type: ignore[arg-type]
        agents=((FirmwareAgentFake() if agent is None else agent),),
        knowledge_gateway=gateway,  # type: ignore[arg-type]
        memory_retriever=retriever,  # type: ignore[arg-type]
        memory_binding=binding,
    )


def _fallback_trace(result: AgentResult) -> list[dict[str, object]]:
    return result.metadata.get("fallback_trace", [])  # type: ignore[return-value]


def test_retriever_failure_continues_through_knowledge_and_dispatch() -> None:
    retriever = RecordingRetriever(error=RuntimeError("private database path"))
    gateway = RecordingGateway()
    planner = RecordingPlanner()
    agent = FirmwareAgentFake()
    supervisor = _supervisor(
        planner=planner,
        retriever=retriever,
        gateway=gateway,
        binding=_memory_binding(),
        agent=agent,
    )

    result = supervisor.run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert (retriever.calls, gateway.calls, planner.context_calls, agent.calls) == (
        1,
        1,
        1,
        1,
    )
    assert planner.contexts[0].memory_context is None
    assert planner.contexts[0].knowledge_context is not None
    assert result.metadata["memory_trace"][-1] == {
        "event": "retrieval_failed",
        "memory_count": 0,
    }
    assert _fallback_trace(result) == [
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


def test_knowledge_failure_uses_memory_only_context() -> None:
    retriever = RecordingRetriever()
    gateway = RecordingGateway(error=RuntimeError("private network endpoint"))
    planner = RecordingPlanner()
    result = _supervisor(
        planner=planner,
        retriever=retriever,
        gateway=gateway,
        binding=_memory_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert planner.contexts[0].knowledge_context is None
    assert planner.contexts[0].memory_context is not None
    assert _fallback_trace(result) == [
        {
            "event": "knowledge_failed",
            "stage": "KnowledgeUnavailable",
            "memory_count": 1,
        },
        {
            "event": "fallback_used",
            "stage": "KnowledgeUnavailable",
            "memory_count": 1,
        },
    ]


def test_memory_and_knowledge_failure_use_empty_planning_context() -> None:
    retriever = RecordingRetriever(error=RuntimeError("private record details"))
    gateway = RecordingGateway(error=RuntimeError("private knowledge payload"))
    planner = RecordingPlanner()
    result = _supervisor(
        planner=planner,
        retriever=retriever,
        gateway=gateway,
        binding=_memory_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert retriever.calls == gateway.calls == planner.context_calls == 1
    assert planner.contexts[0].knowledge_context is None
    assert planner.contexts[0].memory_context is None
    assert [event["event"] for event in _fallback_trace(result)] == [
        "memory_failed",
        "fallback_used",
        "knowledge_failed",
        "fallback_used",
    ]


def test_fusion_failure_discards_context_and_uses_legacy_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_fusion(**_: object) -> EngineeringPlanningContext:
        raise ValueError("private fingerprint mismatch")

    monkeypatch.setattr(
        supervisor_agent_module,
        "build_engineering_planning_context",
        reject_fusion,
    )
    planner = RecordingPlanner()
    result = _supervisor(
        planner=planner,
        retriever=RecordingRetriever(),
        gateway=RecordingGateway(),
        binding=_memory_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert planner.context_calls == 0
    assert planner.legacy_calls == 1
    assert _fallback_trace(result)[-2:] == [
        {
            "event": "fusion_failed",
            "stage": "FusionUnavailable",
            "memory_count": 0,
        },
        {
            "event": "fallback_used",
            "stage": "FusionUnavailable",
            "memory_count": 0,
        },
    ]


@pytest.mark.parametrize("context_result", ("raise", "invalid"))
def test_context_planner_failure_uses_legacy_once(context_result: str) -> None:
    planner = RecordingPlanner(context_result=context_result)
    result = _supervisor(
        planner=planner,
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert planner.context_calls == 1
    assert planner.legacy_calls == 1
    assert _fallback_trace(result)[-1] == {
        "event": "fallback_used",
        "stage": "FusionUnavailable",
        "memory_count": 0,
    }


def test_missing_context_planner_method_uses_legacy_once() -> None:
    planner = LegacyOnlyPlanner()
    result = _supervisor(
        planner=planner,
        retriever=RecordingRetriever(),
        binding=_memory_binding(),
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert planner.legacy_calls == 1
    assert _fallback_trace(result)[-1] == {
        "event": "fallback_used",
        "stage": "FusionUnavailable",
        "memory_count": 0,
    }


def test_no_memory_binding_preserves_knowledge_failure_behavior() -> None:
    gateway = RecordingGateway(error=RuntimeError("private knowledge payload"))
    planner = RecordingPlanner()
    result = _supervisor(planner=planner, gateway=gateway).run(_task())

    assert result.status is AgentStatus.ERROR
    assert result.metadata["execution_summary"]["error_type"] == (
        "SupervisorKnowledgeError"
    )
    assert "fallback_trace" not in result.metadata
    assert planner.context_calls == planner.legacy_calls == 0


def test_fallback_trace_is_strict_frozen_and_does_not_leak_failures() -> None:
    event = SupervisorFallbackTraceEvent(
        event="memory_failed",
        stage="MemoryUnavailable",
        memory_count=0,
    )
    assert tuple(SupervisorFallbackTraceEvent.model_fields) == (
        "event",
        "stage",
        "memory_count",
    )
    with pytest.raises(ValidationError):
        event.memory_count = 1  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SupervisorFallbackTraceEvent(
            event="memory_failed",
            stage="MemoryUnavailable",
            memory_count=0,
            exception="private traceback",  # type: ignore[call-arg]
        )

    result = _supervisor(
        planner=RecordingPlanner(),
        retriever=RecordingRetriever(error=RuntimeError("C:\\private\\db.sqlite")),
        gateway=RecordingGateway(error=RuntimeError("token=private")),
        binding=_memory_binding(),
    ).run(_task())
    serialized = result.model_dump_json()
    assert "private" not in serialized
    assert "token" not in serialized
    assert "db.sqlite" not in serialized
    assert all(
        set(item) == {"event", "stage", "memory_count"}
        for item in _fallback_trace(result)
    )


def test_fallback_does_not_mutate_inputs_or_retry_dependencies() -> None:
    task = _task()
    binding = _memory_binding()
    memory = _memory_context()
    snapshots = (
        copy.deepcopy(task.model_dump(mode="json")),
        copy.deepcopy(binding.model_dump(mode="json")),
        copy.deepcopy(memory.model_dump(mode="json")),
    )
    retriever = RecordingRetriever(result=memory)
    gateway = RecordingGateway(error=RuntimeError("knowledge unavailable"))
    planner = RecordingPlanner(context_result="raise")

    result = _supervisor(
        planner=planner,
        retriever=retriever,
        gateway=gateway,
        binding=binding,
    ).run(task)

    assert result.status is AgentStatus.SUCCESS
    assert task.model_dump(mode="json") == snapshots[0]
    assert binding.model_dump(mode="json") == snapshots[1]
    assert memory.model_dump(mode="json") == snapshots[2]
    assert retriever.calls == gateway.calls == planner.context_calls == 1
    assert planner.legacy_calls == 1
