from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.context import ChatMessage
from embedded_copilot.copilot.models import (
    ChatRole,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.workspace import WorkspaceFile

NOW = datetime(2026, 7, 26, 8, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "message_id",
    (
        "sk-privatecredential",
        "ghp_0123456789abcdefghijklmnop",
        "AKIAIOSFODNN7EXAMPLE",
        "xoxb-1234567890-abcdefghijklmnop",
    ),
)
def test_identifiers_reject_credential_tokens(message_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatMessage(
            message_id=message_id,
            role=ChatRole.USER,
            content_summary="Review an existing engineering Artifact.",
            created_at=NOW,
        )


@pytest.mark.parametrize(
    "summary",
    (
        "gpio_set_level(4, 1);",
        "AAECAwQ=",
        "ghp_0123456789abcdefghijklmnop",
        "AKIAIOSFODNN7EXAMPLE",
        "xoxb-1234567890-abcdefghijklmnop",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue",
        "temperature=0.7",
        "top_p: 0.9",
        "model=private-model",
        "base_url=https://provider.invalid/v1",
    ),
)
def test_safe_summaries_reject_source_binary_and_credentials(summary: str) -> None:
    with pytest.raises(ValidationError):
        ChatMessage(
            message_id="message:1",
            role=ChatRole.USER,
            content_summary=summary,
            created_at=NOW,
        )


def test_workspace_filename_rejects_credential_configuration() -> None:
    with pytest.raises(ValidationError):
        WorkspaceFile(
            file_id="file:1",
            filename="api_key=sk-privatecredential.txt",
            file_type=WorkspaceFileType.OTHER,
            size_bytes=0,
            source=WorkspaceFileSource.INPUT,
            status=WorkspaceFileStatus.UPLOADED,
            created_at=NOW,
        )
