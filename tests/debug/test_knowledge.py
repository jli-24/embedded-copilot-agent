import pytest

from embedded_copilot.debug.exceptions import DebugKnowledgeError
from embedded_copilot.debug.knowledge import (
    DebugKnowledgeRetriever,
    debug_evidence_provenance,
)
from embedded_copilot.debug.models import DebugRequest
from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource


def _request() -> DebugRequest:
    return DebugRequest(
        input="ESP32 watchdog reset PRIVATE_FULL_LOG_SENTINEL",
        platform="ESP32",
        error_type="runtime_crash",
        logs=["watchdog reset PRIVATE_FULL_LOG_SENTINEL"],
    )


def _result() -> KnowledgeResult:
    return KnowledgeResult(
        id="watchdog-doc",
        title="Watchdog Notes",
        content="PRIVATE_KNOWLEDGE_BODY watchdog diagnostic guidance",
        source=KnowledgeSource.LOCAL,
        score=0.9,
        metadata={"category": "runtime", "nested": {"keep": True}},
    )


def test_debug_knowledge_retriever_without_backend_returns_empty() -> None:
    assert DebugKnowledgeRetriever().retrieve(_request()) == []


class _SearchBackend:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.result = _result()

    def search(self, query: str):
        self.queries.append(query)
        return [self.result]


def test_debug_knowledge_retriever_searches_safe_query_and_converts_evidence() -> None:
    backend = _SearchBackend()

    evidence = DebugKnowledgeRetriever(backend).retrieve(_request())

    assert backend.queries == ["ESP32 runtime_crash reset watchdog"]
    assert "PRIVATE_FULL_LOG_SENTINEL" not in backend.queries[0]
    assert evidence[0].source == "LOCAL:watchdog-doc"
    assert evidence[0].content.startswith("PRIVATE_KNOWLEDGE_BODY")
    assert evidence[0].category == "runtime"
    assert debug_evidence_provenance(evidence[0]) == {
        "id": "watchdog-doc",
        "title": "Watchdog Notes",
        "source": "LOCAL",
        "category": "runtime",
        "score": 0.9,
    }
    assert "PRIVATE_KNOWLEDGE_BODY" not in str(
        debug_evidence_provenance(evidence[0])
    )


class _RetrieveBackend:
    def __init__(self) -> None:
        self.query: str | None = None

    def retrieve(self, query: str):
        self.query = query
        return []


def test_debug_knowledge_retriever_supports_retrieve_only_backend() -> None:
    backend = _RetrieveBackend()

    assert DebugKnowledgeRetriever(backend).retrieve(_request()) == []
    assert backend.query == "ESP32 runtime_crash reset watchdog"


def test_debug_knowledge_retriever_does_not_touch_retrieve_when_search_exists() -> None:
    class _SearchPriorityBackend:
        def search(self, query: str):
            return []

        @property
        def retrieve(self):
            raise RuntimeError("retrieve must not be inspected")

    assert DebugKnowledgeRetriever(_SearchPriorityBackend()).retrieve(_request()) == []


def test_debug_knowledge_retriever_isolates_nested_result_metadata() -> None:
    backend = _SearchBackend()

    evidence = DebugKnowledgeRetriever(backend).retrieve(_request())
    backend.result.metadata["nested"]["keep"] = False  # type: ignore[index]

    assert evidence[0].metadata["knowledge_metadata"] == {
        "category": "runtime",
        "nested": {"keep": True},
    }


@pytest.mark.parametrize("result", [object(), {"id": "bad"}])
def test_debug_knowledge_retriever_rejects_malformed_results(result: object) -> None:
    class _MalformedBackend:
        def search(self, query: str):
            return [result]

    with pytest.raises(DebugKnowledgeError, match="retrieval failed"):
        DebugKnowledgeRetriever(_MalformedBackend()).retrieve(_request())


def test_debug_knowledge_retriever_wraps_backend_exception() -> None:
    class _FailingBackend:
        def search(self, query: str):
            raise RuntimeError("private C:/Users/secret/knowledge")

    with pytest.raises(DebugKnowledgeError, match="retrieval failed"):
        DebugKnowledgeRetriever(_FailingBackend()).retrieve(_request())


def test_debug_knowledge_retriever_rejects_backend_without_query_method() -> None:
    with pytest.raises(DebugKnowledgeError, match="search or retrieve"):
        DebugKnowledgeRetriever(object()).retrieve(_request())


def test_debug_knowledge_retriever_wraps_backend_property_exception() -> None:
    class _PropertyBackend:
        @property
        def search(self):
            raise RuntimeError("PRIVATE C:/Users/private/backend")

    with pytest.raises(DebugKnowledgeError, match="retrieval failed"):
        DebugKnowledgeRetriever(_PropertyBackend()).retrieve(_request())


@pytest.mark.parametrize("field", ["id", "title"])
def test_debug_knowledge_retriever_rejects_path_like_provenance(
    field: str,
) -> None:
    result = _result().model_copy(update={field: "C:/Users/private/document"})

    class _PathBackend:
        def search(self, query: str):
            return [result]

    with pytest.raises(DebugKnowledgeError, match="retrieval failed"):
        DebugKnowledgeRetriever(_PathBackend()).retrieve(_request())
