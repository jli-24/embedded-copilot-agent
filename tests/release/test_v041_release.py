from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v041_release_metadata_and_documentation_are_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.41.0.md").read_text(encoding="utf-8")

    assert project["version"] == __version__ == Settings().version == "0.41.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.41.0"
    assert "# Embedded Copilot v0.41.0" in changelog
    assert "# Embedded Copilot v0.41.0" in release
    assert "## v0.41 Architecture" in readme
    assert "## v0.41 Highlights" in readme
    assert "## v0.41 Knowledge Intelligence Layer" in architecture
    for heading in (
        "## Release Overview",
        "## Knowledge Intelligence Layer",
        "## Verification Model",
        "## Knowledge Graph",
        "## Memory Learning Bridge",
        "## Security Boundary",
        "## Non Goals",
    ):
        assert heading in release
    for stage in (
        "External Knowledge Source",
        "Knowledge Candidate Evidence",
        "Knowledge Verification",
        "Verified Knowledge Evidence",
        "Knowledge Graph Projection",
        "Supervisor Planning Context",
        "Engineering Memory Bridge",
    ):
        assert stage in readme
    for phrase in (
        "KnowledgeProvenance",
        "Verified Evidence",
        "Memory Bridge",
        "Supervisor",
        "read-only",
    ):
        assert phrase in release
    for non_goal in (
        "Neo4j",
        "browser",
        "自动 PDF 下载",
        "自主搜索循环",
        "自动 Memory mutation",
    ):
        assert non_goal in release
