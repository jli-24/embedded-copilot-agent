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
from embedded_copilot.knowledge.providers import KnowledgeProvider

__all__ = [
    "DocumentMetadata",
    "KnowledgeQuery",
    "KnowledgeGatewayError",
    "KnowledgeProvider",
    "KnowledgeProviderError",
    "KnowledgeResult",
    "KnowledgeRetriever",
    "KnowledgeSource",
]
