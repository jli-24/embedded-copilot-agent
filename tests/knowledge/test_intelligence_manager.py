from __future__ import annotations

from dataclasses import dataclass

import pytest

from embedded_copilot.copilot.events import KnowledgeTrace as CopilotKnowledgeTrace
from embedded_copilot.copilot.models import KnowledgeTraceAction
from embedded_copilot.knowledge.manager import (
    KnowledgeIntelligenceError,
    KnowledgeManager,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.retriever import (
    GatewayKnowledgeRetriever,
    HybridKnowledgeRetriever,
)
from embedded_copilot.knowledge.source import (
    KnowledgeEvidence,
    KnowledgeSourceType,
)
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace
from embedded_copilot.schemas.result import SourceCitation
from embedded_copilot.rag.retriever import RetrievedChunk


def _result(
    identifier: str,
    source: KnowledgeSource = KnowledgeSource.LOCAL,
    *,
    content: str = "Verified-looking text still requires Engineering Agent validation.",
    score: float | None = 0.8,
    source_type: str | None = None,
    original_source_id: str | None = None,
) -> KnowledgeResult:
    metadata: dict[str, object] = {}
    if source_type is not None:
        metadata["source_type"] = source_type
    if original_source_id is not None:
        metadata["original_source_id"] = original_source_id
    return KnowledgeResult(
        id=identifier,
        title=f"{identifier} title",
        content=content,
        source=source,
        score=score,
        metadata=metadata,
    )


@dataclass
class _Retriever:
    results: list[KnowledgeResult]

    def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        return list(self.results)


@pytest.mark.parametrize(
    ("result", "expected"),
    (
        (
            _result("datasheet:1", source_type="datasheet"),
            KnowledgeSourceType.DATASHEET,
        ),
        (
            _result("official:1", source_type="official_doc"),
            KnowledgeSourceType.OFFICIAL_DOC,
        ),
        (_result("github:1", KnowledgeSource.GITHUB), KnowledgeSourceType.GITHUB),
        (_result("web:1", KnowledgeSource.WEB), KnowledgeSourceType.WEB),
        (_result("upload:1"), KnowledgeSourceType.USER_UPLOAD),
        (
            _result(
                "generated:1",
                source_type="generated",
                original_source_id="datasheet:1",
            ),
            KnowledgeSourceType.GENERATED,
        ),
    ),
)
def test_manager_projects_all_source_types_without_promoting_facts(
    result: KnowledgeResult,
    expected: KnowledgeSourceType,
) -> None:
    retrieval = KnowledgeManager(_Retriever([result])).retrieve(
        KnowledgeQuery(query="ESP32 evidence")
    )

    assert retrieval.evidence[0].source_type is expected
    assert retrieval.evidence[0].source_id == result.id
    assert retrieval.trace.source_ids == (result.id,)
    assert retrieval.trace.action is KnowledgeTraceAction.VIEWED
    assert not hasattr(KnowledgeManager, "promote")
    assert not hasattr(KnowledgeManager, "create_artifact_evidence")


def test_manager_bounds_summary_and_preserves_trace_binding() -> None:
    first = _result("source:1", content="  alpha\n" + ("x" * 700))
    duplicate = _result("SOURCE:1", content="Duplicate candidate")

    retrieval = KnowledgeManager(_Retriever([first, duplicate])).retrieve(
        KnowledgeQuery(query="ESP32 evidence")
    )

    assert len(retrieval.evidence) == 1
    assert len(retrieval.evidence[0].summary) == 512
    assert retrieval.trace.source_ids == ("source:1",)
    assert retrieval.trace.result_count == 1


def test_manager_returns_bound_empty_trace() -> None:
    retrieval = KnowledgeManager(_Retriever([])).retrieve(
        KnowledgeQuery(query="missing evidence")
    )

    assert retrieval.evidence == ()
    assert retrieval.trace.source_ids == ()
    assert retrieval.trace.result_count == 0


def test_manager_rejects_unsafe_or_malformed_candidates_without_leakage() -> None:
    unsafe = _result("source:1", content="api_key=SECRET_SENTINEL")

    with pytest.raises(
        KnowledgeIntelligenceError,
        match="knowledge candidate is unsafe",
    ) as captured:
        KnowledgeManager(_Retriever([unsafe])).retrieve(
            KnowledgeQuery(query="ESP32 evidence")
        )

    assert "SECRET_SENTINEL" not in str(captured.value)


def test_generated_source_requires_original_source_binding() -> None:
    generated = _result("generated:1", source_type="generated")

    with pytest.raises(
        KnowledgeIntelligenceError,
        match="knowledge candidate is unsafe",
    ):
        KnowledgeManager(_Retriever([generated])).retrieve(
            KnowledgeQuery(query="derived candidate")
        )


def test_gateway_adapter_isolates_query_and_results() -> None:
    class Gateway:
        def __init__(self) -> None:
            self.query: KnowledgeQuery | None = None

        def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
            self.query = query
            return [_result("source:1")]

    gateway = Gateway()
    query = KnowledgeQuery(query="ESP32", metadata={"chip": "ESP32-S3"})
    original = query.model_dump(mode="python")

    results = GatewayKnowledgeRetriever(gateway).retrieve(query)

    assert results[0].id == "source:1"
    assert query.model_dump(mode="python") == original
    assert gateway.query is not query


def test_hybrid_adapter_maps_chunks_without_persisting_body() -> None:
    class Hybrid:
        def retrieve(
            self,
            query: str,
            *,
            top_k: int,
            score_threshold: float,
        ) -> list[RetrievedChunk]:
            return [
                RetrievedChunk(
                    chunk_id="chunk:1",
                    text="ESP32-S3 official reference summary.",
                    citation=SourceCitation(
                        source="espressif-doc",
                        filename="esp32-s3.pdf",
                        page=2,
                        chunk_id="chunk:1",
                        score=0.9,
                    ),
                )
            ]

    results = HybridKnowledgeRetriever(Hybrid(), score_threshold=0.2).retrieve(
        KnowledgeQuery(query="ESP32-S3", top_k=2)
    )

    assert results == [
        KnowledgeResult(
            id="chunk:1",
            title="esp32-s3.pdf",
            content="ESP32-S3 official reference summary.",
            source=KnowledgeSource.LOCAL,
            score=0.9,
            metadata={"source_type": "user_upload"},
        )
    ]


def test_shared_trace_is_the_original_copilot_contract() -> None:
    assert CopilotKnowledgeTrace is KnowledgeTrace
    assert set(KnowledgeTrace.model_fields) == {
        "query",
        "source_ids",
        "result_count",
        "action",
    }


def test_knowledge_evidence_forbids_extra_engineering_fields() -> None:
    with pytest.raises(ValueError):
        KnowledgeEvidence.model_validate(
            {
                "source_id": "source:1",
                "source_type": "datasheet",
                "summary": "Candidate source summary.",
                "relevance_score": 0.8,
                "gpio": 4,
            }
        )
