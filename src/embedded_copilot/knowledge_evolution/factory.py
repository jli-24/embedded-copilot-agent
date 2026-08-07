from .adapters.fake import FakeKnowledgeEvolutionPort, FakeKnowledgeRetrievalPort


def create_knowledge_ports() -> tuple[None, None]:
    return None, None


__all__ = [
    "FakeKnowledgeEvolutionPort",
    "FakeKnowledgeRetrievalPort",
    "create_knowledge_ports",
]
