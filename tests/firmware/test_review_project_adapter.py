from __future__ import annotations

from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.firmware.review.models import (
    FirmwareFinding,
    FirmwareFunction,
    FirmwareReviewResult,
)
from embedded_copilot.firmware.review.project_adapter import (
    FirmwareReviewProjectAdapter,
)


def test_review_project_adapter_preserves_contract_without_source_leakage() -> None:
    review = FirmwareReviewResult(
        files=("main.c", "camera.c"),
        platform="ESP32",
        framework="ESP-IDF",
        entrypoints=("app_main",),
        functions=(
            FirmwareFunction(
                name="app_main",
                filename="main.c",
                line=4,
                calls=("camera_init",),
            ),
        ),
        initialization_flow=("app_main -> camera_init",),
        findings=(
            FirmwareFinding(
                rule_id="freertos-task-starvation",
                severity="high",
                description="Potential task starvation.",
                recommendation="Add a bounded blocking or yield operation.",
                source_ids=("attachment:main#line:8",),
                filename="main.c",
                line=8,
            ),
        ),
        limitations=("Macro expansion was not evaluated.",),
        source_ids=("attachment:main", "attachment:camera"),
    )

    project = FirmwareReviewProjectAdapter().to_project(review)

    assert isinstance(project, FirmwareProject)
    assert project.platform == "ESP32"
    assert [item.path for item in project.files] == ["main.c", "camera.c"]
    assert all(item.content == "Source content redacted." for item in project.files)
    assert "Architecture: app_main -> camera_init" in project.structure
    assert any("[HIGH] freertos-task-starvation" in item for item in project.structure)
    serialized = project.model_dump_json()
    assert "PRIVATE_SOURCE_SENTINEL" not in serialized
    assert "attachment:main" in serialized
    assert project.metadata["analysis_mode"] == "deterministic_static_review"
