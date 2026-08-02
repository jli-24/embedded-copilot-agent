from __future__ import annotations

from pathlib import Path


def test_v048_release_documentation_is_complete() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.48.0.md").read_text(encoding="utf-8")
    development = Path("docs/v0.48-optimization.md").read_text(encoding="utf-8")

    assert "Embedded Copilot Agent v0.48.0" in readme
    assert "## v0.48 Optimization Layer" in readme
    assert "## v0.48 Highlights" in readme
    assert "# Embedded Copilot v0.48.0" in changelog
    assert "# Embedded Copilot v0.48.0" in release
    assert "Status: Released" in development
    for historical_heading in (
        "## v0.45 Architecture",
        "## v0.46 Architecture",
        "## v0.47 Hardware Intelligence Layer",
    ):
        assert historical_heading in readme


def test_v048_release_documents_optimization_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.48.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Optimization Runtime",
        "exact registry",
        "PID",
        "Power",
        "Performance",
        "Deterministic Evaluation Projection",
        "Human Approval",
        "Replay Protection",
        "Security Boundary",
    ):
        assert marker in combined

    for heading in (
        "## Overview",
        "## Architecture",
        "## Optimization Runtime",
        "## Mathematical Algorithms",
        "## Evaluation Projection",
        "## Approval Flow",
        "## Security Boundary",
        "## Non Goals",
        "## Testing Evidence",
    ):
        assert heading in release

    for limitation in (
        "mathematical candidate only",
        "no hardware control",
        "no real tuning",
        "no measurement capability",
    ):
        assert limitation in combined
