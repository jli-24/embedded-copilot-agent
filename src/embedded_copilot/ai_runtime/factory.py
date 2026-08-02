"""AI Runtime composition factory."""

from __future__ import annotations

from embedded_copilot.ai_runtime.contracts import EngineeringKnowledgePort
from embedded_copilot.ai_runtime.integration.reasoning import (
    ReasoningEngineeringModelPort,
)
from embedded_copilot.ai_runtime.runtime import AIRuntime, _EngineeringChatService
from embedded_copilot.conversation.reasoning import ReasoningPort


def create_ai_runtime(
    *,
    reasoning_port: ReasoningPort,
    knowledge_port: EngineeringKnowledgePort | None = None,
    max_attempts: int = 2,
) -> AIRuntime:
    if not isinstance(reasoning_port, ReasoningPort):
        raise TypeError("reasoning_port is invalid")
    if knowledge_port is not None and not isinstance(
        knowledge_port, EngineeringKnowledgePort
    ):
        raise TypeError("knowledge_port is invalid")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts is invalid")
    model_port = ReasoningEngineeringModelPort(reasoning_port)
    service = _EngineeringChatService(
        model_port=model_port,
        knowledge_port=knowledge_port,
        max_attempts=max_attempts,
    )
    return AIRuntime._compose(service)


def adapt_knowledge_intelligence_port(port: object) -> EngineeringKnowledgePort:
    from embedded_copilot.ai_runtime.integration.knowledge import (
        KnowledgeIntelligenceAdapter,
    )

    return KnowledgeIntelligenceAdapter(port)


def project_engineering_workspace(workspace: object):
    from embedded_copilot.ai_runtime.integration.product import (
        project_engineering_workspace as project,
    )

    return project(workspace)
