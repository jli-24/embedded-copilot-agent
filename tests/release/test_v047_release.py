from __future__ import annotations

from pathlib import Path


def test_v047_release_documentation_is_complete() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.47.0.md").read_text(encoding="utf-8")
    development = Path("docs/v0.47-hardware-intelligence.md").read_text(
        encoding="utf-8"
    )

    assert "v0.47.0" in readme
    assert "## v0.47 Hardware Intelligence Layer" in readme
    assert "## v0.47 Highlights" in readme
    assert "# Embedded Copilot v0.47.0" in changelog
    assert "# Embedded Copilot v0.47.0" in release
    assert "Status: Released" in development
    for historical_version in (
        "v0.40.0",
        "v0.41.0",
        "v0.42.0",
        "v0.43.0",
        "v0.44.0",
        "v0.45.0",
        "v0.46.0",
    ):
        assert historical_version in readme
        assert historical_version in changelog


def test_v047_release_documents_hardware_boundaries_and_non_goals() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.47.0.md").read_text(encoding="utf-8")
    combined = "\n".join((readme, release))

    for marker in (
        "Hardware Intelligence Runtime",
        "Digital Twin Boundary",
        "HIL Projection Boundary",
        "Hardware Observation",
        "Validation Projection",
        "Execution Integration",
        "Security Boundary",
    ):
        assert marker in combined

    for heading in (
        "## Release Overview",
        "## Hardware Intelligence Architecture",
        "## Digital Twin Layer",
        "## HIL Projection Layer",
        "## Telemetry Model",
        "## Validation Boundary",
        "## Execution Integration",
        "## Security Boundary",
        "## Non-goals",
        "## Validation Results",
    ):
        assert heading in release

    for non_goal in (
        "physical hardware control",
        "USB",
        "Serial",
        "Flash",
        "Debug",
        "real HIL execution",
        "physical hardware validation",
    ):
        assert non_goal in combined
