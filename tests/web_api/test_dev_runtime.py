from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from embedded_copilot.web_api import (
    WebAttachmentProjectionRequest,
    WebAttachmentType,
    WebProjectCreateRequest,
    WebProjectNotFound,
)
from embedded_copilot.web_api.dev import (
    DemoAttachmentProjectionPort,
    DemoPreparationPort,
    DemoProductWorkspacePort,
    InMemoryWebProjectRepository,
)
from embedded_copilot.web_api.dev_server import app

NOW = datetime(2026, 8, 12, 8, 0, tzinfo=UTC)


def test_dev_server_exposes_deterministic_project_dashboard() -> None:
    assert isinstance(app, FastAPI)
    client = TestClient(app)

    first = client.post(
        "/api/projects",
        json={"requirement": "Design a low-power WiFi camera"},
    )
    second = client.post(
        "/api/projects",
        json={"requirement": "Design a low-power WiFi camera"},
    )

    assert first.status_code == 201
    assert first.json() == second.json()
    assert first.json()["project_id"] == "demo-project"
    assert first.json()["current_stage"] == "ARCHITECTURE"

    project = client.get("/api/projects/demo-project")
    dashboard = client.get("/api/projects/demo-project/dashboard")
    timeline = client.get("/api/projects/demo-project/timeline")
    report = client.get("/api/projects/demo-project/report")

    assert project.status_code == 200
    assert dashboard.status_code == 200
    assert dashboard.json()["overall_progress"] == pytest.approx(100.0 / 9.0)
    assert [item["stage"] for item in dashboard.json()["stages"]] == [
        "REQUIREMENT",
        "ARCHITECTURE",
        "HARDWARE",
        "FIRMWARE",
        "VALIDATION",
        "ARTIFACT",
        "EXECUTION",
        "FEEDBACK",
        "OPTIMIZATION",
    ]
    assert timeline.status_code == 200
    assert len(timeline.json()["events"]) == 1
    assert report.status_code == 200
    assert report.json()["project_summary"] == "Design a low-power WiFi camera"


def test_dev_chat_and_attachment_routes_are_projection_only() -> None:
    client = TestClient(app)
    chat = client.post("/api/chat", json={"message": "Prepare a camera project"})
    assert chat.status_code == 200
    assert chat.json()["project"]["project_id"] == "demo-project"

    attachment = client.post(
        "/api/projects/demo-project/attachments",
        json={
            "reference_id": "datasheet-1",
            "attachment_type": "DATASHEET_PDF",
            "basename": "esp32-s3.pdf",
            "summary": "Datasheet metadata only",
            "size_bytes": 4096,
            "observed_at": "2026-08-12T08:00:00Z",
        },
    )

    assert attachment.status_code == 201
    assert attachment.json()["basename"] == "esp32-s3.pdf"
    assert set(attachment.json()).isdisjoint(
        {"content", "payload", "bytes", "path", "mime_type"}
    )


def test_dev_v13_firmware_and_build_are_projection_only() -> None:
    client = TestClient(app)
    client.post("/api/projects", json={"requirement": "Camera"})
    generated = client.post(
        "/api/firmware/generate",
        json={
            "project_id": "demo-project",
            "request_id": "demo-firmware",
            "requested_at": NOW.isoformat(),
        },
    )
    started = client.post(
        "/api/build/start",
        json={
            "build_id": "demo-build",
            "firmware_request_id": "demo-firmware",
            "approval_reference_id": "demo-approval",
            "requested_at": NOW.isoformat(),
        },
    )

    assert generated.status_code == 200
    assert generated.json()["candidate_semantics"] == "unverified"
    assert started.status_code == 200
    assert started.json()["result"]["status"] == "BLOCKED"
    assert started.json()["result"]["diagnostic_codes"] == [
        "BUILD_APPROVAL_REQUIRED"
    ]
    assert "command" not in started.text.lower()


def test_demo_ports_are_deterministic_and_do_not_mutate_inputs() -> None:
    preparation = DemoPreparationPort()
    product = DemoProductWorkspacePort()
    attachment = DemoAttachmentProjectionPort()
    web_request = WebProjectCreateRequest(requirement="Deterministic camera")
    before = web_request.model_copy(deep=True)

    prepared = tuple(preparation.prepare(web_request) for _ in range(10))
    workspaces = tuple(product.create_project(item) for item in prepared)

    assert all(item == prepared[0] for item in prepared)
    assert all(item == workspaces[0] for item in workspaces)
    assert web_request == before

    attachment_request = WebAttachmentProjectionRequest(
        project_id="demo-project",
        session_id="demo-session",
        reference_id="datasheet-1",
        attachment_type=WebAttachmentType.DATASHEET_PDF,
        basename="device.pdf",
        summary="Safe metadata",
        size_bytes=512,
        observed_at=NOW,
    )
    projected = tuple(attachment.project(attachment_request) for _ in range(10))
    assert all(item == projected[0] for item in projected)


def test_in_memory_repository_is_explicit_process_local_state() -> None:
    product = DemoProductWorkspacePort()
    request = DemoPreparationPort().prepare(
        WebProjectCreateRequest(requirement="Repository isolation")
    )
    workspace = product.create_project(request)
    first = InMemoryWebProjectRepository()
    second = InMemoryWebProjectRepository()

    first.save(workspace)
    loaded = first.load(workspace.project_id)

    assert loaded == workspace
    assert loaded is not workspace
    with pytest.raises(WebProjectNotFound):
        second.load(workspace.project_id)
