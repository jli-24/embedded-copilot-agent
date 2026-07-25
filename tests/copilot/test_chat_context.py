from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.context import ChatMessage
from embedded_copilot.copilot.models import (
    ChatRole,
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)

NOW = datetime(2026, 7, 26, 8, 0, tzinfo=timezone.utc)


def test_chat_message_is_summary_only_and_immutable() -> None:
    message = ChatMessage(
        message_id="message:1",
        role=ChatRole.USER,
        content_summary="Request review of an existing MQ-2 proposal.",
        created_at=NOW,
        references=["artifact:1", "decision:1"],
    )

    assert message.references == ("artifact:1", "decision:1")
    assert set(ChatMessage.model_fields) == {
        "message_id",
        "role",
        "content_summary",
        "created_at",
        "references",
    }
    with pytest.raises(ValidationError):
        message.content_summary = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "summary",
    (
        "x" * 513,
        "line one\nline two",
        r"Read C:\Users\private\main.c",
        "void app_main(void) { gpio_set_level(4, 1); }",
        "api_key=sk-privatecredential",
        "provider=OpenAI model_name=gpt-private",
        "pdf_content=confidential datasheet excerpt",
        "source_code=int main(void);",
        "binary_data=AAECAwQ=",
        "password: privatecredential",
        "credential=privatecredential",
        "provider: OpenAI",
        "model_name: private-model",
        b"binary chat content",
    ),
)
def test_chat_message_rejects_raw_or_sensitive_content(summary: object) -> None:
    with pytest.raises(ValidationError):
        ChatMessage(
            message_id="message:1",
            role=ChatRole.USER,
            content_summary=summary,
            created_at=NOW,
        )


def test_chat_message_cannot_embed_artifact_or_domain_changes() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(
            message_id="message:1",
            role=ChatRole.USER,
            content_summary="Request an MQ-2 design review.",
            created_at=NOW,
            artifact={"components": ["MQ-2"]},
        )


def test_model_request_is_provider_agnostic_contract_only() -> None:
    request = ModelRequest(
        task_type=ModelTaskType.REASONING,
        input_type=ModelInputType.TEXT,
        context_ids=["session:1", "artifact:1"],
    )

    assert request.context_ids == ("session:1", "artifact:1")
    assert set(ModelRequest.model_fields) == {
        "task_type",
        "input_type",
        "context_ids",
    }
    for extra in (
        {"model_name": "gpt"},
        {"provider": "openai"},
        {"api_key": "sk-private"},
        {"endpoint": "https://provider.invalid"},
    ):
        with pytest.raises(ValidationError):
            ModelRequest(
                task_type=ModelTaskType.CHAT,
                input_type=ModelInputType.TEXT,
                context_ids=("session:1",),
                **extra,
            )


def test_model_request_requires_unique_context_references() -> None:
    for context_ids in ((), ("session:1", "SESSION:1")):
        with pytest.raises(ValidationError):
            ModelRequest(
                task_type=ModelTaskType.CHAT,
                input_type=ModelInputType.TEXT,
                context_ids=context_ids,
            )
