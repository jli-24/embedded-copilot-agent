from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v130_release_metadata_is_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert project["version"] == "1.3.0"
    assert __version__ == "1.3.0"
    assert Settings(_env_file=None).version == "1.3.0"
    assert HealthResponse(status="ok", mode="offline").version == "1.3.0"


def test_v130_release_note_states_execution_boundaries() -> None:
    release = Path("docs/releases/v1.3.0.md").read_text(encoding="utf-8")

    for marker in (
        "# Embedded Copilot v1.3.0 Release",
        "Engineering Execution Layer",
        "ESPIdfBuildExecutionPort",
        "Engineering Observation Layer",
        "does not execute shell commands",
        "does not write files",
        "does not control hardware",
    ):
        assert marker in release
