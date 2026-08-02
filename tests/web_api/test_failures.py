from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from embedded_copilot.product import create_product_runtime
from embedded_copilot.web_api import (
    WebAttachmentProjection,
    create_web_api_app,
    web_attachment_fingerprint,
)


@dataclass
class _UnavailablePreparation:
    def prepare(self, request):
        raise RuntimeError("provider C:/private failure payload")


@dataclass
class _Repository:
    def save(self, workspace):
        raise AssertionError("save must not run")

    def load(self, project_id):
        raise RuntimeError("database password path")


@dataclass
class _Attachment:
    def project(self, request):
        raise RuntimeError("device path")


def test_unknown_project_and_dependency_failures_are_sanitized(web_setup) -> None:
    client, _, _, _ = web_setup
    missing = client.get("/api/projects/missing/report")
    assert missing.status_code == 404
    assert missing.json()["code"] == "PROJECT_NOT_FOUND"
    assert "missing" not in missing.text

    app = create_web_api_app(
        product_port=create_product_runtime().product_workspace_port(),
        preparation_port=_UnavailablePreparation(),
        repository_port=_Repository(),
        attachment_port=_Attachment(),
    )
    unavailable = TestClient(app).post(
        "/api/projects", json={"requirement": "private requirement"}
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "WEB_DEPENDENCY_UNAVAILABLE"
    assert "private" not in unavailable.text
    assert "provider" not in unavailable.text


def test_request_validation_does_not_echo_private_input(web_setup) -> None:
    client, _, _, _ = web_setup
    response = client.post(
        "/api/projects",
        json={"requirement": "secret requirement", "payload": "secret payload"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "WEB_REQUEST_REJECTED"
    assert "secret" not in response.text


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    (("project_id", "other-project"), ("basename", "C:/private/device.pdf")),
)
def test_attachment_output_is_revalidated_and_bound(
    web_setup, field: str, unsafe_value: str
) -> None:
    client, _, _, attachment = web_setup
    client.post("/api/projects", json={"requirement": "Camera"})

    def unsafe_project(request):
        values = dict(
            project_id=request.project_id,
            session_id=request.session_id,
            reference_id=request.reference_id,
            attachment_type=request.attachment_type,
            basename=request.basename,
            summary=request.summary,
            size_bytes=request.size_bytes,
            observed_at=request.observed_at,
            source_fingerprint=request.fingerprint,
        )
        values[field] = unsafe_value
        return WebAttachmentProjection(
            **values,
            fingerprint=web_attachment_fingerprint(**values),
        )

    attachment.project = unsafe_project
    response = client.post(
        "/api/projects/project-1/attachments",
        json={
            "reference_id": "datasheet-1",
            "attachment_type": "DATASHEET_PDF",
            "basename": "device.pdf",
            "summary": "Safe metadata",
            "size_bytes": 100,
            "observed_at": "2026-08-12T08:00:00Z",
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "WEB_DEPENDENCY_UNAVAILABLE"
    assert "private" not in response.text
