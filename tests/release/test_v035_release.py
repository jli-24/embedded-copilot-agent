from __future__ import annotations

from pathlib import Path

import tomllib


def test_v035_release_documents_observation_only_debug_boundary() -> None:
    release = Path("docs/release/v0.35.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.35.0" in release
    assert "observation-only" in release
    assert "does not implement a hardware transport" in release
    assert "Workspace Runtime remains the only file write boundary" in release
    assert "v0.35 Embedded Debug Runtime" in architecture


def test_v035_does_not_add_hardware_sdk_or_transport_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    dependencies = tuple(value.casefold() for value in project["dependencies"])

    forbidden = ("pyserial", "pylink", "pyocd", "openocd", "cmsis")
    assert not any(value.startswith(forbidden) for value in dependencies)
