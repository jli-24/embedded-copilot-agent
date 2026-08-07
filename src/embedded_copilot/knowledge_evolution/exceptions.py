class KnowledgeEvolutionError(RuntimeError):
    code = "KNOWLEDGE_UNAVAILABLE"


class KnowledgeUnavailable(KnowledgeEvolutionError):
    code = "KNOWLEDGE_UNAVAILABLE"


class KnowledgeRejected(KnowledgeEvolutionError):
    code = "QUERY_REJECTED"


class KnowledgeNotFound(KnowledgeEvolutionError):
    code = "KNOWLEDGE_NOT_FOUND"


class RetrievalUnavailable(KnowledgeEvolutionError):
    code = "RETRIEVAL_UNAVAILABLE"


__all__ = [
    "KnowledgeEvolutionError",
    "KnowledgeNotFound",
    "KnowledgeRejected",
    "KnowledgeUnavailable",
    "RetrievalUnavailable",
]
