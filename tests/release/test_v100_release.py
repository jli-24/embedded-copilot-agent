from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v100_active_release_metadata_is_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    health = HealthResponse(status="ok", mode="offline")
    health_schema = HealthResponse.model_json_schema()

    assert project["version"] == __version__ == Settings().version == "1.3.0"
    assert health.version == "1.3.0"
    assert health_schema["properties"]["version"]["const"] == "1.3.0"
    assert health_schema["properties"]["version"]["default"] == "1.3.0"


def test_v100_product_release_documentation_is_prepared() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    demo = Path("docs/demo/esp32-s3-smart-camera.md").read_text(encoding="utf-8")

    for marker in (
        "Embedded Copilot v1.0.0",
        "AI Embedded Engineer",
        "EngineeringWorkspace",
        "EngineeringReleaseReport",
    ):
        assert marker in readme

    assert changelog.startswith("# Changelog\n\n## v1.0.0")
    assert "### Added" in changelog
    assert "### Completed" in changelog
    assert "### Validation" in changelog
    for marker in (
        "Engineering Workspace",
        "Project Session",
        "Dashboard Projection",
        "Timeline Projection",
        "Release Report",
    ):
        assert marker in changelog

    for marker in (
        "ESP32-S3 Smart Camera Demo",
        "Requirement",
        "Hardware Proposal",
        "Firmware Proposal",
        "Validation Plan",
        "Artifact",
        "Execution",
        "Optimization",
        "Release Report",
    ):
        assert marker in demo


def test_v100_release_note_is_complete_and_bounded() -> None:
    release = Path("docs/releases/v1.0.0.md").read_text(encoding="utf-8")

    for heading in (
        "# Embedded Copilot v1.0.0 Release",
        "## Overview",
        "## Architecture",
        "## Major Features",
        "## Engineering Workflow",
        "## Validation Results",
        "## Security Model",
        "## Demo",
    ):
        assert heading in release

    for marker in (
        "proposal-first",
        "human approval",
        "safe execution boundary",
        "ESP32-S3 Smart Camera",
        "2565 passed, 6 skipped",
    ):
        assert marker in release

    for non_goal in (
        "不自动制造",
        "不自动修改 PCB",
        "不提供无人值守硬件控制",
    ):
        assert non_goal in release
