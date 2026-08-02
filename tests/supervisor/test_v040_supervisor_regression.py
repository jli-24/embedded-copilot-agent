from __future__ import annotations

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.engineering_memory.context import MemoryTrustBasis

from .test_context_fusion import (
    _fuse,
    _knowledge_context,
    _memory_context,
    _source,
)
from .test_failure_fallback import (
    FirmwareAgentFake as FallbackAgent,
    RecordingGateway as FallbackGateway,
    RecordingPlanner as FallbackPlanner,
    RecordingRetriever as FallbackRetriever,
    _memory_binding as _fallback_binding,
    _supervisor as _fallback_supervisor,
    _task as _fallback_task,
)
from .test_memory_supervisor_integration import (
    RecordingKnowledgeGateway,
    RecordingRetriever,
    _memory_binding,
    _supervisor,
    _task,
)


def test_v040_fusion_matrix_confidence_and_fingerprints_are_stable() -> None:
    knowledge = _knowledge_context(_source(trust_level=0.8))
    memory = _memory_context(trust_basis=MemoryTrustBasis.HUMAN_APPROVAL)
    cases = (
        (knowledge, None, 0.8),
        (None, memory, 0.5),
        (knowledge, memory, 0.5),
        (None, None, 0.0),
    )

    for knowledge_context, memory_context, expected_confidence in cases:
        first = _fuse(knowledge=knowledge_context, memory=memory_context)
        second = _fuse(knowledge=knowledge_context, memory=memory_context)
        assert first == second
        assert first.confidence == expected_confidence
        assert first.context_fingerprint == second.context_fingerprint

    changed_knowledge = _knowledge_context(_source("datasheet-changed"))
    changed_memory = _memory_context(usage=50)
    baseline = _fuse(knowledge=knowledge, memory=memory)
    assert _fuse(
        knowledge=changed_knowledge,
        memory=memory,
    ).context_fingerprint != (
        baseline.context_fingerprint
    )
    assert _fuse(
        knowledge=knowledge,
        memory=changed_memory,
    ).context_fingerprint != (
        baseline.context_fingerprint
    )


def test_v040_memory_enabled_pipeline_retrieves_fuses_plans_and_dispatches_once() -> None:
    retriever = RecordingRetriever()
    gateway = RecordingKnowledgeGateway()
    supervisor, planner, agent = _supervisor(
        retriever=retriever,
        binding=_memory_binding(),
        gateway=gateway,
    )

    result = supervisor.run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert len(retriever.requests) == 1
    assert len(gateway.queries) == 1
    assert planner.legacy_calls == 0
    assert len(planner.contexts) == 1
    assert planner.contexts[0].knowledge_context is not None
    assert planner.contexts[0].memory_context is not None
    assert len(agent.tasks) == 1


def test_v040_no_memory_configuration_preserves_legacy_planning() -> None:
    supervisor, planner, agent = _supervisor()

    result = supervisor.run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert planner.legacy_calls == 1
    assert planner.contexts == []
    assert len(agent.tasks) == 1
    assert "memory_trace" not in result.metadata
    assert "fallback_trace" not in result.metadata


def test_v040_failure_matrix_has_no_retry_and_keeps_safe_progress() -> None:
    cases = (
        (
            FallbackRetriever(error=RuntimeError("private memory")),
            FallbackGateway(),
            FallbackPlanner(),
            (1, 1, 1, 0),
        ),
        (
            FallbackRetriever(),
            FallbackGateway(error=RuntimeError("private knowledge")),
            FallbackPlanner(),
            (1, 1, 1, 0),
        ),
        (
            FallbackRetriever(error=RuntimeError("private memory")),
            FallbackGateway(error=RuntimeError("private knowledge")),
            FallbackPlanner(),
            (1, 1, 1, 0),
        ),
        (
            FallbackRetriever(),
            FallbackGateway(),
            FallbackPlanner(context_result="raise"),
            (1, 1, 1, 1),
        ),
    )

    for retriever, gateway, planner, expected in cases:
        agent = FallbackAgent()
        supervisor = _fallback_supervisor(
            planner=planner,
            retriever=retriever,
            gateway=gateway,
            binding=_fallback_binding(),
            agent=agent,
        )
        result = supervisor.run(_fallback_task())
        assert result.status is AgentStatus.SUCCESS
        assert (
            retriever.calls,
            gateway.calls,
            agent.calls,
            planner.legacy_calls,
        ) == expected
        assert planner.context_calls <= 1
