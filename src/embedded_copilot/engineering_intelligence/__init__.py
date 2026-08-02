"""Framework-independent Engineering Intelligence Layer."""

from embedded_copilot.engineering_intelligence.contracts import (
    EngineeringIntelligencePort,
    WebResearchPort,
)
from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceError,
    EngineeringIntelligenceRejected,
    EngineeringKnowledgeUnavailable,
)
from embedded_copilot.engineering_intelligence.facade import (
    EngineeringIntelligenceRuntime,
)
from embedded_copilot.engineering_intelligence.factory import (
    create_engineering_intelligence_runtime,
)
from embedded_copilot.engineering_intelligence.integration.datasheet import (
    project_datasheet_knowledge,
)
from embedded_copilot.engineering_intelligence.integration.knowledge import (
    project_verified_knowledge,
)
from embedded_copilot.engineering_intelligence.integration.memory import (
    project_verified_memory,
)
from embedded_copilot.engineering_intelligence.integration.project import (
    project_engineering_project,
)
from embedded_copilot.engineering_intelligence.models import (
    DatasheetKnowledgeCategory,
    DatasheetKnowledgeProjection,
    EngineeringContextRequest,
    EngineeringContextSnapshot,
    EngineeringDecisionProjection,
    EngineeringIntelligenceProgressEvent,
    EngineeringIntelligenceRequest,
    EngineeringIntelligenceSnapshot,
    EngineeringIntelligenceStage,
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EngineeringProgressStatus,
    EngineeringProjectContextProjection,
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
    EngineeringRequirementRequest,
    EngineeringTask,
    EngineeringTaskDomain,
    EstimatedEffort,
    EvidenceStatus,
    RequirementConstraint,
    WebResearchRequest,
    WebResearchResult,
    WebResearchTopic,
    engineering_evidence_fingerprint,
)

__all__ = (
    "DatasheetKnowledgeCategory",
    "DatasheetKnowledgeProjection",
    "EngineeringContextRequest",
    "EngineeringContextSnapshot",
    "EngineeringDecisionProjection",
    "EngineeringIntelligenceError",
    "EngineeringIntelligencePort",
    "EngineeringIntelligenceProgressEvent",
    "EngineeringIntelligenceRejected",
    "EngineeringIntelligenceRequest",
    "EngineeringIntelligenceRuntime",
    "EngineeringIntelligenceSnapshot",
    "EngineeringIntelligenceStage",
    "EngineeringKnowledgeEvidence",
    "EngineeringKnowledgeSourceType",
    "EngineeringKnowledgeUnavailable",
    "EngineeringProgressStatus",
    "EngineeringProjectContextProjection",
    "EngineeringProjectPlan",
    "EngineeringRequirementDocument",
    "EngineeringRequirementRequest",
    "EngineeringTask",
    "EngineeringTaskDomain",
    "EstimatedEffort",
    "EvidenceStatus",
    "RequirementConstraint",
    "WebResearchPort",
    "WebResearchRequest",
    "WebResearchResult",
    "WebResearchTopic",
    "create_engineering_intelligence_runtime",
    "engineering_evidence_fingerprint",
    "project_datasheet_knowledge",
    "project_engineering_project",
    "project_verified_knowledge",
    "project_verified_memory",
)
