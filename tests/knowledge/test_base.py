from collections.abc import Sequence

from embedded_copilot.knowledge.base import KnowledgeRetriever


class MemoryRetriever:
    def search(self, query: str) -> Sequence[str]:
        return [query]

    def add_documents(self, documents: Sequence[str]) -> None:
        self.documents = list(documents)


def test_knowledge_retriever_protocol_is_runtime_checkable() -> None:
    retriever = MemoryRetriever()

    assert isinstance(retriever, KnowledgeRetriever)
    assert retriever.search("SPI") == ["SPI"]


def test_knowledge_retriever_has_public_import() -> None:
    from embedded_copilot.knowledge import KnowledgeRetriever as PublicRetriever

    assert PublicRetriever is KnowledgeRetriever
