from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v047_release_metadata_is_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    health_schema = HealthResponse.model_json_schema()

    assert project["version"] == __version__ == Settings().version == "0.47.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.47.0"
    assert health_schema["properties"]["version"]["const"] == "0.47.0"
    assert health_schema["properties"]["version"]["default"] == "0.47.0"


def test_v047_release_documentation_is_complete() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.47.0.md").read_text(encoding="utf-8")
    development = Path("docs/v0.47-hardware-intelligence.md").read_text(
        encoding="utf-8"
    )

    assert "Embedded Copilot Agent v0.47.0" in readme
    assert "## v0.47 Hardware Intelligence Layer" in readme
    assert "## v0.47 Highlights" in readme
    assert "# Embedded Copilot v0.47.0" in changelog
    assert "# Embedded Copilot v0.47.0" in release
    assert "Status: Released" in development
    for historical_version in (
        "v0.40.0",
        "v0.41.0",
        "v0.42.0",
        "v0.43.0",
        "v0.44.0",
        "v0.45.0",
        "v0.46.0",
    ):
        assert historical_version in readme
        assert historical_version in changelog


def test_v047_release_documents_hardware_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.47.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Hardware Intelligence Runtime",
        "Digital Twin Boundary",
        "HIL Projection Boundary",
        "Hardware Observation",
        "Validation Projection",
        "Execution Integration",
        "Security Boundary",
    ):
        assert marker in combined

    for heading in (
        "## Release Overview",
        "## Hardware Intelligence Architecture",
        "## Digital Twin Layer",
        "## HIL Projection Layer",
        "## Telemetry Model",
        "## Validation Boundary",
        "## Execution Integration",
        "## Security Boundary",
        "## Non-goals",
        "## Validation Results",
    ):
        assert heading in release

    for non_goal in (
        "physical hardware control",
        "USB",
        "Serial",
        "Flash",
        "Debug",
        "real HIL execution",
        "physical hardware validation",
    ):
        assert non_goal in combined
