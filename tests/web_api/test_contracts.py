from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.web_api import (
    WebAttachmentProjectionRequest,
    WebAttachmentType,
    WebProjectCreateRequest,
    canonical_web_json,
)


def test_web_request_is_frozen_strict_and_fingerprinted() -> None:
    request = WebProjectCreateRequest(requirement="Design an ESP32-S3 camera")

    assert request.fingerprint.startswith("sha256:")
    assert canonical_web_json(request) == canonical_web_json(
        WebProjectCreateRequest(requirement="Design an ESP32-S3 camera")
    )
    with pytest.raises(ValidationError):
        WebProjectCreateRequest.model_validate(
            {"requirement": "camera", "unexpected": "private"}
        )
    with pytest.raises(ValidationError):
        request.requirement = "changed"


def test_attachment_contract_rejects_path_and_naive_time() -> None:
    with pytest.raises(ValidationError):
        WebAttachmentProjectionRequest(
            project_id="project-1",
            session_id="session-1",
            reference_id="attachment-1",
            attachment_type=WebAttachmentType.DATASHEET_PDF,
            basename="C:/private/device.pdf",
            summary="Datasheet metadata",
            size_bytes=100,
            observed_at=datetime(2026, 8, 12, 8, 0),
        )

    request = WebAttachmentProjectionRequest(
        project_id="project-1",
        session_id="session-1",
        reference_id="attachment-1",
        attachment_type=WebAttachmentType.DATASHEET_PDF,
        basename="device.pdf",
        summary="Datasheet metadata",
        size_bytes=100,
        observed_at=datetime(2026, 8, 12, 8, 0, tzinfo=UTC),
    )
    assert request.basename == "device.pdf"
