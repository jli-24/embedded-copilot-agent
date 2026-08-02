from __future__ import annotations


def test_create_and_read_project_projections(web_setup) -> None:
    client, preparation, repository, _ = web_setup

    created = client.post(
        "/api/projects",
        json={"requirement": "Design an ESP32-S3 smart camera"},
    )
    assert created.status_code == 201
    reference = created.json()
    assert reference["project_id"] == "project-1"
    assert reference["project_name"] == "ESP32-S3 Smart Camera"
    assert reference["current_stage"] == "EXECUTION"
    assert len(preparation.calls) == 1
    assert repository.saves == 1

    detail = client.get("/api/projects/project-1")
    dashboard = client.get("/api/projects/project-1/dashboard")
    timeline = client.get("/api/projects/project-1/timeline")
    report = client.get("/api/projects/project-1/report")

    assert detail.status_code == dashboard.status_code == 200
    assert timeline.status_code == report.status_code == 200
    assert detail.json()["project"]["project_id"] == "project-1"
    assert dashboard.json()["overall_progress"] == 8 * 100.0 / 9
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
    assert all("raw" not in str(item).lower() for item in timeline.json()["events"])
    assert report.json()["project_id"] == "project-1"
    assert repository.loads == 4


def test_chat_reuses_project_creation_pipeline(web_setup) -> None:
    client, preparation, repository, _ = web_setup

    response = client.post(
        "/api/chat",
        json={"message": "Design a low-power WiFi camera"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Project Created"
    assert response.json()["current_stage"] == "EXECUTION"
    assert len(preparation.calls) == 1
    assert repository.saves == 1


def test_attachment_route_projects_metadata_only(web_setup) -> None:
    client, _, _, attachment = web_setup
    client.post("/api/projects", json={"requirement": "Camera"})

    response = client.post(
        "/api/projects/project-1/attachments",
        json={
            "reference_id": "datasheet-1",
            "attachment_type": "DATASHEET_PDF",
            "basename": "esp32-s3.pdf",
            "summary": "ESP32-S3 datasheet metadata",
            "size_bytes": 4096,
            "observed_at": "2026-08-12T08:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["basename"] == "esp32-s3.pdf"
    assert set(body).isdisjoint({"content", "bytes", "path", "base64"})
    assert len(attachment.calls) == 1
