from __future__ import annotations

from pathlib import Path


def test_v046_release_documentation_is_complete() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.46.0.md").read_text(encoding="utf-8")
    development = Path("docs/v0.46-execution-integration.md").read_text(
        encoding="utf-8"
    )

    assert "v0.46.0" in readme
    assert "## v0.46 Architecture" in readme
    assert "## v0.46 Highlights" in readme
    assert "# Embedded Copilot v0.46.0" in changelog
    assert "# Embedded Copilot v0.46.0" in release
    assert "Status: Released" in development
    for historical_version in (
        "v0.40.0",
        "v0.41.0",
        "v0.42.0",
        "v0.43.0",
        "v0.44.0",
        "v0.45.0",
    ):
        assert historical_version in readme
        assert historical_version in changelog


def test_v046_release_documents_execution_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.46.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Execution Runtime",
        "Executor Registry Boundary",
        "Execution Plan",
        "Human Approval Binding",
        "Controlled Execution Lifecycle",
        "Verification Projection",
        "Failure Snapshot",
        "Replay Protection",
        "Security Boundary",
    ):
        assert marker in combined

    for heading in (
        "## Release Overview",
        "## Execution Integration Architecture",
        "## Executor Registry Boundary",
        "## Execution Plan",
        "## Human Approval Binding",
        "## Controlled Execution Lifecycle",
        "## Verification Projection",
        "## Failure Snapshot",
        "## Replay Protection",
        "## Progress Event Isolation",
        "## Security Boundary",
        "## Validation",
        "## Non Goals",
    ):
        assert heading in release

    for non_goal in (
        "real Build",
        "real Flash",
        "real Hardware Debug",
        "Shell",
        "Git",
        "network",
        "filesystem mutation",
        "hardware control",
        "cross-process replay protection",
    ):
        assert non_goal in release
