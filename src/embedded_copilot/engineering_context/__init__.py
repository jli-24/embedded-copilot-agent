"""Read-only deterministic engineering context assembly."""

from .contracts import (
    ApprovedMemoryProjectionPort,
    DatasheetMetadataProjectionPort,
    EngineeringContextProviderPort,
    EngineeringGraphProjectionPort,
    KnowledgeEvolutionProjectionPort,
)
from .exceptions import (
    EngineeringContextError,
    EngineeringContextRejected,
    EngineeringContextUnavailable,
)
from .factory import create_engineering_context_service
from .fusion import ContextFusionService
from .models import (
    ApprovedMemoryProjection,
    ContextSourceReference,
    DatasheetMetadataProjection,
    EngineeringContextItem,
    EngineeringContextQuery,
    EngineeringContextSnapshot,
    VerifiedKnowledgeProjection,
)
from .policy import ContextCategory, ContextPolicy, ContextSourceType
from .retrieval import EngineeringContextRetrievalService
from .service import EngineeringContextService

__all__ = (
    "ApprovedMemoryProjection",
    "ApprovedMemoryProjectionPort",
    "ContextCategory",
    "ContextFusionService",
    "ContextPolicy",
    "ContextSourceReference",
    "ContextSourceType",
    "DatasheetMetadataProjection",
    "DatasheetMetadataProjectionPort",
    "EngineeringContextError",
    "EngineeringContextItem",
    "EngineeringContextProviderPort",
    "EngineeringContextQuery",
    "EngineeringContextRejected",
    "EngineeringContextRetrievalService",
    "EngineeringContextService",
    "EngineeringContextSnapshot",
    "EngineeringContextUnavailable",
    "EngineeringGraphProjectionPort",
    "KnowledgeEvolutionProjectionPort",
    "VerifiedKnowledgeProjection",
    "create_engineering_context_service",
)
