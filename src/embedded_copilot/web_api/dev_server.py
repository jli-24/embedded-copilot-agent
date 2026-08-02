"""Uvicorn entry point for the deterministic local Web Console demo.

Run with::

    uvicorn embedded_copilot.web_api.dev_server:app --reload --port 18080
"""

from embedded_copilot.ai_runtime import create_ai_runtime
from embedded_copilot.conversation_feedback import (
    create_conversation_feedback_service,
)
from embedded_copilot.core.config import Settings
from embedded_copilot.model_runtime import create_model_runtime
from embedded_copilot.web_api import create_web_api_app
from embedded_copilot.web_api.dev import (
    DemoAttachmentProjectionPort,
    DemoPreparationPort,
    DemoProductWorkspacePort,
    InMemoryWebProjectRepository,
)

_model_runtime = create_model_runtime(Settings())
_ai_runtime = create_ai_runtime(
    reasoning_port=_model_runtime.reasoning_port(),
)

app = create_web_api_app(
    product_port=DemoProductWorkspacePort(),
    preparation_port=DemoPreparationPort(),
    repository_port=InMemoryWebProjectRepository(),
    attachment_port=DemoAttachmentProjectionPort(),
    engineering_chat_port=_ai_runtime.engineering_chat_port(),
    feedback_port=create_conversation_feedback_service().feedback_port(),
)
