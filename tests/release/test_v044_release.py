from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v044_release_metadata_is_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    health_schema = HealthResponse.model_json_schema()

    assert project["version"] == __version__ == Settings().version == "0.44.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.44.0"
    assert health_schema["properties"]["version"]["const"] == "0.44.0"
    assert health_schema["properties"]["version"]["default"] == "0.44.0"


def test_v044_release_documentation_is_complete() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.44.0.md").read_text(encoding="utf-8")
    development = Path("docs/v0.44-engineering-generation.md").read_text(
        encoding="utf-8"
    )

    assert "Embedded Copilot Agent v0.44.0" in readme
    assert "## v0.44 Architecture" in readme
    assert "## v0.44 Highlights" in readme
    assert "# Embedded Copilot v0.44.0" in changelog
    assert "# Embedded Copilot v0.44.0" in release
    assert "Status: Released" in development
    for historical_version in ("v0.40.0", "v0.41.0", "v0.42.0", "v0.43.0"):
        assert historical_version in readme
        assert historical_version in changelog


def test_v044_release_documents_generation_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.44.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Engineering Generation Runtime",
        "Generator Registry Boundary",
        "Hardware Design Proposal",
        "Firmware Proposal",
        "PCB Design Proposal",
        "BOM Proposal",
        "Artifact Verification Boundary",
        "Human Approval Boundary",
        "Security Isolation",
    ):
        assert marker in combined

    for heading in (
        "## Release Overview",
        "## Engineering Generation Architecture",
        "## Generator Registry",
        "## Artifact Proposal",
        "## Hardware Design Generation",
        "## Firmware Generation",
        "## PCB Proposal Generation",
        "## BOM Proposal",
        "## Verification Boundary",
        "## Human Approval",
        "## Security Boundary",
        "## Validation",
        "## Non Goals",
    ):
        assert heading in release

    for non_goal in (
        "real PCB files",
        "project files",
        "Build",
        "Flash",
        "Hardware Debug",
        "Tool Runtime",
    ):
        assert non_goal in release
