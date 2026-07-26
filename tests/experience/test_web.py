from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from web.copilot.app_pages.blueprint import graphviz_source
from web.copilot.app_pages.files import DISPLAY_COLUMNS
from web.copilot.client import CopilotExperienceClient
from web.copilot.navigation import PAGE_TITLES

ROOT = Path(__file__).parents[2]
ALLOWED_SESSION_STATE_KEYS = {
    "session_id",
    "answer_summary",
    "attachment_receipt",
    "handoff",
    "review_receipt",
    "vision_suggestion",
}


def test_streamlit_experience_loads_workspace_as_the_default_page() -> None:
    app = AppTest.from_file(str(ROOT / "web" / "copilot" / "streamlit_app.py"))
    app.run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "Workspace"
    assert PAGE_TITLES == (
        "Workspace",
        "Chat",
        "Upload",
        "Vision",
        "Blueprint",
        "Evidence",
        "Files",
        "Progress",
        "Review",
        "Model Status",
    )


@pytest.mark.parametrize(
    ("module_name", "expected_title"),
    (
        ("workspace", "Workspace"),
        ("chat", "Chat"),
        ("upload", "Upload"),
        ("vision", "Vision"),
        ("blueprint", "Blueprint"),
        ("evidence", "Evidence"),
        ("files", "Files"),
        ("progress", "Progress"),
        ("review", "Review"),
        ("model_status", "Model Status"),
    ),
)
def test_each_streamlit_page_loads_with_only_allowed_session_state(
    module_name: str,
    expected_title: str,
) -> None:
    app = AppTest.from_string(
        f"from web.copilot.app_pages.{module_name} import render\nrender()",
    )
    app.run(timeout=15)

    assert not app.exception
    assert app.title[0].value == expected_title
    assert set(app.session_state.filtered_state).issubset(ALLOWED_SESSION_STATE_KEYS)


def test_review_page_shows_engineer_handoff_disclaimer_and_three_actions() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
import web.copilot.app_pages.review as review_page

class Client:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_artifacts(self, session_id):
        return {
            "session_id": session_id,
            "viewer_state": {"status": "READY"},
            "artifacts": [{"artifact_id": "artifact:1"}],
        }

review_page.api_client = lambda: Client()
st.session_state["session_id"] = "session:1"
review_page.render()
""",
    )
    app.run(timeout=15)

    assert not app.exception
    assert "AI Proposal → Engineer Review" in tuple(item.value for item in app.caption)
    assert "记录用户意图，不代表 Artifact 已批准" in tuple(
        item.value for item in app.warning
    )
    assert tuple(item.label for item in app.button) == (
        "Request Review",
        "Approve Intent",
        "Request Change",
    )


@pytest.mark.parametrize(
    ("button_index", "expected_action"),
    (
        (0, "REQUEST_REVIEW"),
        (1, "APPROVE_INTENT"),
        (2, "REQUEST_CHANGE"),
    ),
)
def test_review_buttons_record_the_selected_user_intent(
    button_index: int,
    expected_action: str,
) -> None:
    app = AppTest.from_string(
        """
import streamlit as st
import web.copilot.app_pages.review as review_page

class Client:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_artifacts(self, session_id):
        return {
            "session_id": session_id,
            "viewer_state": {"status": "READY"},
            "artifacts": [{"artifact_id": "artifact:1"}],
        }

    def record_review(
        self,
        session_id,
        *,
        intent_id,
        artifact_id,
        action,
        comment_summary,
        timestamp,
    ):
        return {
            "intent_id": intent_id,
            "session_id": session_id,
            "artifact_id": artifact_id,
            "action": action,
            "source": "user",
            "status": "RECORDED",
            "handoff": "engineering_agent_review",
            "recorded_at": timestamp,
        }

review_page.api_client = lambda: Client()
st.session_state["session_id"] = "session:1"
review_page.render()
""",
    )
    app.run(timeout=15)
    app.button[button_index].click().run(timeout=15)

    assert not app.exception
    assert app.session_state["review_receipt"]["action"] == expected_action
    assert app.session_state["review_receipt"]["session_id"] == "session:1"


def test_conversation_summary_is_not_reused_across_sessions() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
from web.copilot.state import conversation_result, store_conversation_result

store_conversation_result(
    "session:1",
    answer_summary="Session one answer.",
    handoff="engineering_agent_review",
)
answer_summary, handoff = conversation_result("session:2")
st.write(answer_summary or "No cross-session answer.")
st.write(handoff or "No cross-session handoff.")
""",
    )
    app.run(timeout=15)

    assert not app.exception
    assert tuple(item.value for item in app.markdown) == (
        "No cross-session answer.",
        "No cross-session handoff.",
    )
    assert set(app.session_state.filtered_state) == {
        "answer_summary",
        "handoff",
    }


def test_client_uses_only_additive_copilot_api_routes() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"session_id": "session:1"})

    client = CopilotExperienceClient(
        "http://testserver",
        transport=httpx.MockTransport(respond),
    )
    try:
        client.get_workspace("session:1")
        client.get_artifacts("session:1")
        client.get_files("session:1")
        client.get_progress("session:1")
        client.send_message(
            "session:1",
            message_id="message:1",
            summary="Explain the available evidence.",
            created_at="2026-07-26T08:01:00Z",
            references=("image:1",),
        )
        client.bind_attachment(
            "session:1",
            reference_id="image:1",
            input_type="IMAGE",
            basename="schematic.png",
            summary="ESP32 schematic image reference.",
            size_bytes=1024,
            created_at="2026-07-26T08:01:30Z",
        )
        client.analyze_vision(
            "session:1",
            reference_id="image:1",
            message_summary="Review the referenced schematic.",
        )
        client.record_review(
            "session:1",
            intent_id="review:1",
            artifact_id="artifact:1",
            action="REQUEST_REVIEW",
            comment_summary=None,
            timestamp="2026-07-26T08:02:00Z",
        )
    finally:
        client.close()

    assert [(request.method, request.url.path) for request in requests] == [
        ("GET", "/api/v1/copilot/sessions/session:1/workspace"),
        ("GET", "/api/v1/copilot/sessions/session:1/artifact-view"),
        ("GET", "/api/v1/copilot/sessions/session:1/files"),
        ("GET", "/api/v1/copilot/sessions/session:1/progress"),
        ("POST", "/api/v1/copilot/sessions/session:1/messages"),
        ("POST", "/api/v1/copilot/sessions/session:1/attachments"),
        ("POST", "/api/v1/copilot/sessions/session:1/vision"),
        ("POST", "/api/v1/copilot/sessions/session:1/review"),
    ]
    review_payload = json.loads(requests[-1].content)
    assert review_payload["timestamp"] == "2026-07-26T08:02:00Z"
    assert "created_at" not in review_payload
    assert "source" not in review_payload
    assert not hasattr(client, "download")
    assert not hasattr(client, "open")
    assert not hasattr(client, "preview")


def test_client_does_not_route_internal_api_calls_through_environment_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, object] = {}

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            options.update(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr("web.copilot.client.httpx.Client", _Client)

    client = CopilotExperienceClient("http://127.0.0.1:8765")
    client.close()

    assert options["trust_env"] is False


def test_blueprint_graph_uses_only_api_edges_and_marks_empty_relations_unresolved() -> (
    None
):
    projection = {
        "nodes": [
            {"node_id": "node:1", "label": "Controller", "kind": "module"},
            {"node_id": "node:2", "label": "Sensor", "kind": "module"},
        ],
        "edges": [],
    }

    source, state = graphviz_source(projection)

    assert source is None
    assert state == "unresolved"


def test_blueprint_graph_does_not_add_relationships() -> None:
    projection = {
        "nodes": [
            {"node_id": "node:1", "label": "Controller", "kind": "module"},
            {"node_id": "node:2", "label": "Sensor", "kind": "module"},
        ],
        "edges": [
            {
                "edge_id": "edge:1",
                "source_node_id": "node:2",
                "target_node_id": "node:1",
                "label": "reported relation",
            }
        ],
    }

    source, state = graphviz_source(projection)

    assert state == "ready"
    assert source is not None
    assert source.count("->") == 1
    assert '"node:2" -> "node:1"' in source


def test_files_page_has_no_file_access_controls() -> None:
    source = (ROOT / "web" / "copilot" / "app_pages" / "files.py").read_text(
        encoding="utf-8"
    )

    for prohibited in (
        "download_button",
        "file_uploader",
        "open(",
        "preview",
        "file_content",
    ):
        assert prohibited not in source


def test_files_page_uses_only_safe_metadata_columns() -> None:
    assert DISPLAY_COLUMNS == (
        "file_id",
        "basename",
        "file_type",
        "size",
        "source",
        "status",
        "timestamp",
    )


def test_upload_page_registers_references_without_file_bytes() -> None:
    source = (ROOT / "web" / "copilot" / "app_pages" / "upload.py").read_text(
        encoding="utf-8"
    )

    for prohibited in (
        "file_uploader",
        "accept_file",
        "read(",
        "getvalue(",
        "b64encode",
        "content=",
    ):
        assert prohibited not in source


def test_multimodal_state_is_not_reused_across_sessions() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
from web.copilot.state import (
    attachment_receipt,
    store_attachment_receipt,
    store_vision_suggestion,
    vision_suggestion,
)

store_attachment_receipt(
    "session:1",
    {
        "session_id": "session:1",
        "reference_id": "image:1",
        "type": "IMAGE",
        "basename": "schematic.png",
        "summary": "Image reference.",
        "size_bytes": 1,
        "status": "REFERENCED",
        "created_at": "2026-07-26T08:01:00Z",
    },
)
store_vision_suggestion(
    "session:1",
    {"type": "reasoning_suggestion", "summary": "Review required."},
)
st.write(attachment_receipt("session:2") or "No cross-session attachment.")
st.write(vision_suggestion("session:2") or "No cross-session suggestion.")
""",
    )
    app.run(timeout=15)

    assert not app.exception
    assert tuple(item.value for item in app.markdown) == (
        "No cross-session attachment.",
        "No cross-session suggestion.",
    )
