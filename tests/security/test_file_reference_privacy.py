from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from embedded_copilot.api.file_reference_catalog import CopilotFileReferenceCatalog
from embedded_copilot.api.main import create_app
from embedded_copilot.copilot.models import (
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.workspace import WorkspaceFile
from embedded_copilot.file_runtime import (
    FileIntelligenceResponse,
    FileReference,
    FileRuntimeUnavailable,
)
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInput,
    MultimodalInputType,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.services.config import Settings

_PRIVATE_PATH = r"C:\workspace\private\main.py"
_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?<![:/])/(?:[^/\s]+/)+)")


class _ChatService:
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse:
        return ChatResponse(answer="Existing chat.", trace_id=trace_id)


class _SuccessPort:
    async def analyze(self, request):
        return FileIntelligenceResponse(
            summary="SOURCE_CODE file structure: 12 lines, 240 characters."
        )


class _FailurePort:
    async def analyze(self, request):
        try:
            raise FileNotFoundError(_PRIVATE_PATH)
        except FileNotFoundError:
            raise FileRuntimeUnavailable() from None


def _repository() -> ProcessLocalAttachmentBindingRepository:
    repository = ProcessLocalAttachmentBindingRepository()
    repository.bind(
        AttachmentBinding(
            session_id="session:1",
            input=MultimodalInput(
                type=MultimodalInputType.FILE,
                reference_id="file:1",
                summary="Reference metadata.",
            ),
            basename="main.py",
            size_bytes=42,
            created_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        )
    )
    return repository


async def _post(port) -> httpx.Response:
    app = create_app(
        service=_ChatService(),
        workspace_service=None,
        experience_service=None,
        vision_port=None,
        file_port=port,
        settings=Settings(_env_file=None),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/copilot/sessions/session:1/files/analyze",
                json={
                    "file_id": "file:1",
                    "instruction_summary": "Inspect structure.",
                },
            )


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, dict):
        return tuple(item for child in value.values() for item in _string_values(child))
    if isinstance(value, list):
        return tuple(item for child in value for item in _string_values(child))
    return ()


def test_file_reference_string_privacy() -> None:
    catalog = CopilotFileReferenceCatalog(
        _repository(),
        {("session:1", "file:1"): Path("private/main.py")},
    )

    reference = catalog.resolve("session:1", "file:1")

    assert isinstance(reference, FileReference)
    assert reference.relative_path == Path("private/main.py")
    for rendered in (str(reference), repr(reference)):
        assert "relative_path" not in rendered
        assert "private" not in rendered
        assert "main.py" not in rendered
        assert not _PATH_PATTERN.search(rendered)
    assert "relative_path" not in reference.model_dump(mode="json")


def test_file_api_response_and_schema_do_not_expose_path_fields() -> None:
    response = asyncio.run(_post(_SuccessPort()))

    assert response.status_code == 200
    assert set(response.json()) == {"type", "summary", "review_required"}
    assert all(
        not _PATH_PATTERN.search(value) for value in _string_values(response.json())
    )

    app = create_app(
        service=_ChatService(),
        workspace_service=None,
        experience_service=None,
        vision_port=None,
        file_port=_SuccessPort(),
        settings=Settings(_env_file=None),
    )
    schemas = app.openapi()["components"]["schemas"]
    for schema_name in (
        "CopilotFileIntelligenceRequest",
        "CopilotFileIntelligenceResponse",
    ):
        properties = schemas[schema_name]["properties"]
        assert not set(properties) & {
            "path",
            "relative_path",
            "absolute_path",
            "file_url",
        }


def test_file_error_privacy(caplog: pytest.LogCaptureFixture) -> None:
    response = asyncio.run(_post(_FailurePort()))

    assert response.status_code == 503
    assert set(response.json()) == {"error", "trace_id"}
    assert response.json()["error"] == "file_unavailable"
    assert _PRIVATE_PATH not in response.text
    assert "FileNotFoundError" not in response.text
    assert "traceback" not in response.text.casefold()
    assert _PRIVATE_PATH not in caplog.text
    error = FileRuntimeUnavailable()
    assert str(error) == "file_unavailable"
    assert _PRIVATE_PATH not in repr(error)


def test_workspace_and_review_receipt_keep_only_safe_projection() -> None:
    workspace_file = WorkspaceFile(
        file_id="file:1",
        filename="main.py",
        file_type=WorkspaceFileType.SOURCE_CODE,
        size_bytes=42,
        source=WorkspaceFileSource.INPUT,
        status=WorkspaceFileStatus.REFERENCED,
        created_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
    )
    serialized = workspace_file.model_dump(mode="json")
    assert serialized["filename"] == "main.py"
    assert not set(serialized) & {"path", "relative_path", "content", "summary"}

    app = AppTest.from_string(
        """
import json
import streamlit as st
from web.copilot.state import store_review_receipt

projected = store_review_receipt(
    "session:1",
    {
        "intent_id": "review:1",
        "session_id": "session:1",
        "artifact_id": "artifact:1",
        "action": "REQUEST_REVIEW",
        "source": "user",
        "status": "RECORDED",
        "handoff": "engineering_agent_review",
        "recorded_at": "2026-07-26T00:00:00Z",
        "path": r"C:\\workspace\\private\\main.py",
    },
)
st.write(json.dumps(projected, sort_keys=True))
""",
    )
    app.run(timeout=15)

    assert not app.exception
    state = app.session_state["review_receipt"]
    assert "path" not in state
    assert _PRIVATE_PATH not in json.dumps(state)


def test_structural_summary_rejects_path_content() -> None:
    for unsafe in (
        _PRIVATE_PATH,
        "/workspace/private/main.py",
        "SOURCE_CODE file structure: 12 lines, 240 characters. /workspace/main.py",
    ):
        with pytest.raises(ValidationError):
            FileIntelligenceResponse(summary=unsafe)
