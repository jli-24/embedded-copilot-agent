"""Framework-independent structured AI Runtime."""

from embedded_copilot.ai_runtime.contracts import (
    EngineeringChatPort,
    EngineeringKnowledgePort,
)
from embedded_copilot.ai_runtime.exceptions import (
    AIModelUnavailable,
    AIRequestRejected,
    AIRuntimeError,
)
from embedded_copilot.ai_runtime.factory import (
    adapt_knowledge_intelligence_port,
    create_ai_runtime,
    project_engineering_workspace,
)
from embedded_copilot.ai_runtime.models import (
    EngineeringChatContext,
    EngineeringChatRequest,
    EngineeringModelOutput,
    EngineeringResponse,
    KnowledgeEvidenceProjection,
    canonical_ai_json,
    engineering_chat_context_fingerprint,
    engineering_chat_request_fingerprint,
    engineering_model_output_fingerprint,
    engineering_response_fingerprint,
    knowledge_evidence_fingerprint,
)
from embedded_copilot.ai_runtime.runtime import AIRuntime

__all__ = (
    "AIModelUnavailable",
    "AIRequestRejected",
    "AIRuntime",
    "AIRuntimeError",
    "EngineeringChatContext",
    "EngineeringChatPort",
    "EngineeringChatRequest",
    "EngineeringKnowledgePort",
    "EngineeringModelOutput",
    "EngineeringResponse",
    "KnowledgeEvidenceProjection",
    "adapt_knowledge_intelligence_port",
    "canonical_ai_json",
    "create_ai_runtime",
    "engineering_chat_context_fingerprint",
    "engineering_chat_request_fingerprint",
    "engineering_model_output_fingerprint",
    "engineering_response_fingerprint",
    "knowledge_evidence_fingerprint",
    "project_engineering_workspace",
)
