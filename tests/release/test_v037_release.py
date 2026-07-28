from __future__ import annotations

from pathlib import Path

import tomllib

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v037_release_documents_controlled_tool_boundary() -> None:
    release = Path("docs/release/v0.37.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.37.0" in release
    assert "Tool Execution Layer" in release
    assert "permission" in release
    assert "audit" in release
    assert "Mock" in release
    assert "v0.37 Tool Execution Layer" in architecture
    assert "v0.37.0 新增 security-first Tool Execution Layer" in readme
    for non_goal in (
        "autonomous execution",
        "Shell",
        "Flash",
        "hardware control",
        "real build",
        "real firmware test",
    ):
        assert non_goal in release


def test_v037_versions_are_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert project["version"] == "0.37.0"
    assert __version__ == "0.37.0"
    assert Settings().version == "0.37.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.37.0"


def test_v037_keeps_dependency_list_unchanged() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert tuple(project["dependencies"]) == (
        "tree-sitter>=0.25,<0.26",
        "tree-sitter-c>=0.24,<0.25",
        "tree-sitter-cpp>=0.23,<0.24",
    )
