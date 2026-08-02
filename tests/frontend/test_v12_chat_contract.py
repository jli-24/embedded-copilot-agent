from __future__ import annotations

from pathlib import Path


def test_project_dashboard_exposes_structured_chat_and_feedback_controls() -> None:
    dashboard = Path("frontend/src/pages/ProjectDashboardPage.tsx").read_text(
        encoding="utf-8"
    )
    chat = Path("frontend/src/components/EngineeringChatPanel.tsx")

    assert chat.exists()
    source = chat.read_text(encoding="utf-8")
    assert "Engineering AI" in source
    assert "Requirement analysis" in source
    assert "Architecture recommendation" in source
    assert "Risk analysis" in source
    assert "Next action" in source
    assert "Accept" in source
    assert "Correct" in source
    assert "EngineeringChatPanel" in dashboard


def test_chat_ui_uses_response_events_without_streaming_or_hidden_io() -> None:
    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")
    chat = Path("frontend/src/components/EngineeringChatPanel.tsx").read_text(
        encoding="utf-8"
    )

    assert '"/api/chat"' in client
    assert '"/api/feedback"' in client
    assert "response.events" in chat
    for forbidden in (
        "WebSocket",
        "EventSource",
        "FileReader",
        "localStorage",
        "sessionStorage",
    ):
        assert forbidden not in chat

