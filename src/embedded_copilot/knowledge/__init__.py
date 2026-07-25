"""Embedded knowledge metadata, entities, and retrieval contracts."""

from embedded_copilot.knowledge.base import KnowledgeRetriever
from embedded_copilot.knowledge.exceptions import (
    KnowledgeGatewayError,
    KnowledgeProviderError,
)
from embedded_copilot.knowledge.models import (
    DocumentMetadata,
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.knowledge.manager import KnowledgeManager
from embedded_copilot.knowledge.providers import KnowledgeProvider
from embedded_copilot.knowledge.source import (
    KnowledgeEvidence,
    KnowledgeRetrieval,
    KnowledgeSourceType,
)

__all__ = [
    "DocumentMetadata",
    "KnowledgeQuery",
    "KnowledgeGatewayError",
    "KnowledgeEvidence",
    "KnowledgeManager",
    "KnowledgeProvider",
    "KnowledgeProviderError",
    "KnowledgeResult",
    "KnowledgeRetrieval",
    "KnowledgeRetriever",
    "KnowledgeSource",
    "KnowledgeSourceType",
]
