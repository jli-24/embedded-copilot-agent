from __future__ import annotations

from pathlib import Path


def test_v042_release_documentation_is_complete_and_historical() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.42.0.md").read_text(encoding="utf-8")
    workflow = Path("docs/v0.42-agent-workflow.md").read_text(encoding="utf-8")

    assert "v0.42.0 新增 planning-only Agent Workflow Layer" in readme
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
