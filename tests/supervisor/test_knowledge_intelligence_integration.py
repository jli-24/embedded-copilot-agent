from __future__ import annotations

from datetime import UTC, datetime

from embedded_copilot.knowledge.intelligence import (
    EngineeringKnowledgeRequest,
    KnowledgeEntityType,
    KnowledgeIntelligenceResult,
    KnowledgeProvenance,
    KnowledgeSourceType,
    KnowledgeVerificationMethod,
    VerifiedKnowledgeEvidence,
)
from embedded_copilot.supervisor.agent import SupervisorAgent

from .test_memory_supervisor_integration import (
    FirmwareAgentFake,
    RecordingPlanner,
    _task,
)

UTC_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


def _evidence() -> VerifiedKnowledgeEvidence:
    return VerifiedKnowledgeEvidence(
        evidence_id="knowledge-evidence-1",
        entity_type=KnowledgeEntityType.COMPONENT,
        fact_key="component.esp32-s3.identity",
        canonical_value="ESP32-S3",
        summary="ESP32-S3 is the selected component.",
        provenance=(
            KnowledgeProvenance(
                source_type=KnowledgeSourceType.DATASHEET,
                publisher="Espressif",
                reference="datasheet:esp32-s3:section-5.2",
                verification_method=(
                    KnowledgeVerificationMethod.AUTHORITATIVE_SOURCE
                ),
                verified_at=UTC_TIME,
                confidence=1.0,
            ),
        ),
    )


class RecordingKnowledgeIntelligencePort:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[EngineeringKnowledgeRequest] = []

    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> KnowledgeIntelligenceResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError(
                "database path C:\\private\\knowledge.db provider secret"
            )
        return KnowledgeIntelligenceResult(verified_evidence=(_evidence(),))


def test_verified_knowledge_assists_planning_without_entering_agent_handoff() -> None:
    port = RecordingKnowledgeIntelligencePort()
    planner = RecordingPlanner()
    agent = FirmwareAgentFake()
    supervisor = SupervisorAgent(
        planner=planner,  # type: ignore[arg-type]
        agents=(agent,),
        knowledge_intelligence_port=port,  # type: ignore[arg-type]
    )

    result = supervisor.run(_task())

    assert result.status.value == "success"
    assert len(port.requests) == 1
    assert len(planner.contexts) == 1
    assert planner.contexts[0].knowledge_context is not None
    source = planner.contexts[0].knowledge_context.sources[0]
    assert source.source_id == "knowledge-evidence-1"
    assert source.trust_level == 1.0
    serialized_handoff = agent.tasks[0].model_dump_json()
    for forbidden in (
        "graph_evidence_projection",
        "canonical_value",
        "verification_method",
        "memory_proposal",
    ):
        assert forbidden not in serialized_handoff
    assert result.metadata["knowledge_trace"] == [
        {
            "sequence": 1,
            "stage": "retrieval",
            "status": "success",
            "count": 1,
            "source_type": "datasheet",
        }
    ]


def test_knowledge_failure_uses_legacy_planner_and_safe_trace() -> None:
    port = RecordingKnowledgeIntelligencePort(fail=True)
    planner = RecordingPlanner()
    supervisor = SupervisorAgent(
        planner=planner,  # type: ignore[arg-type]
        agents=(FirmwareAgentFake(),),
        knowledge_intelligence_port=port,  # type: ignore[arg-type]
    )

    result = supervisor.run(_task())

    assert result.status.value == "success"
    assert len(port.requests) == 1
    assert len(planner.contexts) == 1
    assert planner.contexts[0].knowledge_context is None
    assert planner.contexts[0].memory_context is None
    assert planner.legacy_calls == 0
    trace = result.metadata["knowledge_trace"]
    assert trace == [
        {
            "sequence": 1,
            "stage": "retrieval",
            "status": "failed",
            "count": 0,
            "source_type": "none",
        }
    ]
    serialized = result.model_dump_json()
    for secret in ("private", "database", "provider", "secret"):
        assert secret not in serialized.casefold()
