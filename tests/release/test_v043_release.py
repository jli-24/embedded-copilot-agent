from __future__ import annotations

from pathlib import Path


def test_v043_release_documentation_is_complete_and_historical() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.43.0.md").read_text(encoding="utf-8")
    execution = Path("docs/v0.43-agent-execution.md").read_text(encoding="utf-8")

    assert "v0.43.0" in readme
    assert "## v0.43 Architecture" in readme
    assert "## v0.43 Highlights" in readme
    assert "# Embedded Copilot v0.43.0" in changelog
    assert "# Embedded Copilot v0.43.0" in release
    assert "Status: Released" in execution
    for historical_version in ("v0.40.0", "v0.41.0", "v0.42.0"):
        assert historical_version in readme
        assert historical_version in changelog


def test_v043_release_documents_execution_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.43.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Controlled Agent Execution Runtime",
        "Explicit Agent Registry Binding",
        "Execution Lifecycle State Machine",
        "Safe Result Projection",
        "Verification Boundary",
        "Fail-safe Execution Snapshot",
        "Two-phase Human Resume",
        "Progress Event Isolation",
        "Security Boundary",
    ):
        assert marker in combined

    for heading in (
        "## Release Overview",
        "## Execution Runtime",
        "## Agent Binding",
        "## Lifecycle",
        "## Verification",
        "## Failure Handling",
        "## Recovery",
        "## Workflow Adapter",
        "## Security Boundary",
        "## Validation Evidence",
        "## Non Goals",
    ):
        assert heading in release

    for non_goal in ("Build", "Flash", "Hardware Debug", "Tool Runtime"):
        assert non_goal in release
