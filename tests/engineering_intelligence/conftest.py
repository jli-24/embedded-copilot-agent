from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_interface import (
    EngineeringProjectProjection,
    engineering_project_fingerprint,
)

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


@pytest.fixture
def interface_project() -> EngineeringProjectProjection:
    references = ("board-esp32-s3",)
    return EngineeringProjectProjection(
        project_id="project-1",
        name="ESP32-S3 Smart Camera",
        summary="A reviewable smart camera engineering project.",
        reference_ids=references,
        fingerprint=engineering_project_fingerprint(
            project_id="project-1",
            name="ESP32-S3 Smart Camera",
            summary="A reviewable smart camera engineering project.",
            reference_ids=references,
        ),
    )
