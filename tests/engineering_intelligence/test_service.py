import asyncio

from embedded_copilot.engineering_intelligence import (
    ContextStage,
    EngineeringContextInputProjection,
    EngineeringIntelligenceRequest,
    create_engineering_intelligence,
    build_context_snapshot,
)
from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource


class _Knowledge:
    def search(self, query):
        return [
            KnowledgeResult(
                id="result-1",
                title="SPI guidance",
                content="PRIVATE DOCUMENT BODY MUST NOT CROSS THE PROJECTION",
                source=KnowledgeSource.LOCAL,
                score=0.9,
            )
        ]


def test_service_projects_local_knowledge_without_content() -> None:
    snapshot = build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.PCB_DESIGN,
            decision_topic="interface",
            constraints=(),
        )
    )
    port = create_engineering_intelligence(
        knowledge_port=_Knowledge()
    ).intelligence_port()
    result = asyncio.run(
        port.query(
            EngineeringIntelligenceRequest(
                project_id="project-1",
                question="Which interface should be reviewed?",
                context_snapshot=snapshot,
            )
        )
    )
    assert result.knowledge_context.evidence[0].summary == "SPI guidance"
    assert "PRIVATE DOCUMENT" not in result.model_dump_json()
    assert result.recommendation.evidence_refs == ("local-result-1",)
