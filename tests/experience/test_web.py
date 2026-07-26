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
    "handoff",
    "review_receipt",
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
            instruction_summary="Review the referenced schematic.",
        )
        client.record_review(
            "session:1",
            intent_id="review:1",
            artifact_id="artifact:1",
            action="REQUEST_REVIEW",
            comment_summary=None,
            timestamp="2026-07-26T08:02:00Z",
        )
        client.get_model_status()
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
        ("GET", "/api/v1/copilot/models/status"),
    ]
    review_payload = json.loads(requests[-2].content)
    vision_payload = json.loads(requests[6].content)
    assert vision_payload == {
        "reference_id": "image:1",
        "instruction_summary": "Review the referenced schematic.",
    }
    assert review_payload["timestamp"] == "2026-07-26T08:02:00Z"
    assert "created_at" not in review_payload
    assert "source" not in review_payload
    assert not hasattr(client, "download")
    assert not hasattr(client, "open")
    assert not hasattr(client, "preview")


def test_model_status_page_loads_request_time_status_without_session_state() -> None:
    app = AppTest.from_string(
        """
import web.copilot.app_pages.model_status as model_status_page

class Client:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get_model_status(self):
        return {
            "provider": "ollama",
            "status": "available",
            "capabilities": ["CHAT", "CODE", "REASONING"],
            "model": "edge-model:latest",
        }

model_status_page.api_client = lambda: Client()
model_status_page.render()
""",
    )
    app.run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "Model Status"
    assert tuple((item.label, item.value) for item in app.metric) == (
        ("Provider", "ollama"),
        ("Status", "available"),
        ("Model", "edge-model:latest"),
    )
    assert set(app.session_state.filtered_state) == set()


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


def test_vision_page_renders_transient_review_required_suggestion() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
import web.copilot.app_pages.vision as vision_page

class Client:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def analyze_vision(
        self,
        session_id,
        *,
        reference_id,
        instruction_summary,
    ):
        return {
            "type": "reasoning_suggestion",
            "summary": "Reference metadata requires engineer review.",
            "review_required": True,
        }

vision_page.api_client = lambda: Client()
st.session_state["session_id"] = "session:1"
vision_page.render()
""",
    )
    app.run(timeout=15)
    app.text_input[1].input("image:1")
    app.text_area[0].input("Review the reference metadata.")
    app.button[0].click().run(timeout=15)

    assert not app.exception
    assert tuple(item.value for item in app.subheader) == ("AI Suggestion",)
    assert "Reference metadata requires engineer review." in tuple(
        item.value for item in app.markdown
    )
    assert tuple(item.value for item in app.warning) == (
        "This output is not Engineering Evidence. Engineer validation required.",
    )
    assert {
        key
        for key in app.session_state.filtered_state
        if not key.startswith("FormSubmitter:")
    } == {"session_id"}


def test_upload_page_renders_transient_reference_receipt() -> None:
    app = AppTest.from_string(
        """
import streamlit as st
import web.copilot.app_pages.upload as upload_page

class Client:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def bind_attachment(self, session_id, **kwargs):
        return {
            "session_id": session_id,
            "reference_id": kwargs["reference_id"],
            "type": kwargs["input_type"],
            "basename": kwargs["basename"],
            "summary": kwargs["summary"],
            "size_bytes": kwargs["size_bytes"],
            "status": "REFERENCED",
            "created_at": kwargs["created_at"],
        }

upload_page.api_client = lambda: Client()
st.session_state["session_id"] = "session:1"
upload_page.render()
""",
    )
    app.run(timeout=15)
    app.text_input[1].input("image:1")
    app.text_input[2].input("schematic.png")
    app.text_area[0].input("Registered image reference metadata.")
    app.number_input[0].set_value(1024)
    app.button[0].click().run(timeout=15)

    assert not app.exception
    assert tuple(item.value for item in app.success) == (
        "Reference metadata registered.",
    )
    assert {
        key
        for key in app.session_state.filtered_state
        if not key.startswith("FormSubmitter:")
    } == {"session_id"}
