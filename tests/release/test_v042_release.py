from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def test_v042_release_metadata_is_synchronized() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    health_schema = HealthResponse.model_json_schema()

    assert project["version"] == __version__ == Settings().version == "0.42.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.42.0"
    assert health_schema["properties"]["version"]["const"] == "0.42.0"
    assert health_schema["properties"]["version"]["default"] == "0.42.0"


def test_v042_release_documentation_is_complete_and_historical() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.42.0.md").read_text(encoding="utf-8")
    workflow = Path("docs/v0.42-agent-workflow.md").read_text(encoding="utf-8")

    assert "Embedded Copilot Agent v0.42.0" in readme
    assert "## v0.42 Architecture" in readme
    assert "## v0.42 Highlights" in readme
    assert "## v0.41 Architecture" in readme
    assert "## v0.40 Architecture" in readme
    assert "# Embedded Copilot v0.42.0" in changelog
    assert "# Embedded Copilot v0.41.0" in changelog
    assert "# Embedded Copilot v0.40.0" in changelog
    assert "# Embedded Copilot v0.42.0" in release
    assert "Status: Released" in workflow

    for heading in (
        "## Release Overview",
        "## Workflow Runtime Foundation",
        "## Context and Risk Projection",
        "## Planning, DAG and Scheduling",
        "## Human Approval",
        "## Progress Events",
        "## Security Boundary",
        "## Validation",
        "## Non Goals",
    ):
        assert heading in release


def test_v042_release_documents_workflow_boundaries() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.42.0.md").read_text(encoding="utf-8")
    workflow = Path("docs/v0.42-agent-workflow.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release, workflow))

    for marker in (
        "Requirement Agent Port",
        "Workflow Context Projection",
        "Risk Projection Boundary",
        "Engineering Planning Agent",
        "Frozen Task DAG",
        "Human Approval",
        "Deterministic Scheduler",
        "Progress Events",
        "Security Boundary",
    ):
        assert marker in combined

    for boundary in (
        "task priority",
        "scheduling order",
        "DAG",
        "dependency",
        "Agent selection",
    ):
        assert boundary in release
