from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v040_release_metadata_and_documentation_are_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.40.0.md").read_text(encoding="utf-8")

    assert project["version"] == __version__ == Settings().version == "0.40.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.40.0"
    assert "# Embedded Copilot v0.40.0" in changelog
    assert "# Embedded Copilot v0.40.0" in release
    assert "Memory Intelligence Layer" in release
    assert "Knowledge Fusion" in release
    assert "Failure-safe Supervisor" in release
    assert "read-side" in release
    assert "## v0.40 Architecture" in readme
    assert "## v0.40 Highlights" in readme
