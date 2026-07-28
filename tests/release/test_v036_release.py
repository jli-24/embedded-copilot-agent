from __future__ import annotations

from pathlib import Path

import tomllib


def test_v036_release_documents_deterministic_telemetry_boundary() -> None:
    release = Path("docs/release/v0.36.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.36.0" in release
    assert "deterministic" in release
    assert "observation-only" in release
    assert "bounded synchronous pull" in release
    assert "endpoint direction" in release
    assert "v0.36 Telemetry Intelligence Layer" in architecture
    for non_goal in (
        "PID optimization",
        "automatic tuning",
        "hardware control",
        "Flash",
        "real transport",
        "hardware validation",
    ):
        assert non_goal in release


def test_v036_does_not_add_analysis_or_hardware_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert tuple(project["dependencies"]) == (
        "tree-sitter>=0.25,<0.26",
        "tree-sitter-c>=0.24,<0.25",
        "tree-sitter-cpp>=0.23,<0.24",
    )
    telemetry_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/embedded_copilot/telemetry_runtime").glob("*.py")
    )
    assert "ControlSignalContext" not in telemetry_source
