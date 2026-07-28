from __future__ import annotations

from pathlib import Path

import tomllib


def test_v034_release_documents_transport_neutral_mcp_boundary() -> None:
    release = Path("docs/release/v0.34.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.34.0" in release
    assert "transport-neutral" in release
    assert "does not start an MCP server" in release
    assert "Workspace Runtime remains the only write boundary" in release
    assert "v0.34 VS Code MCP Integration Layer" in architecture
    assert "VS Code MCP Integration Layer" in readme


def test_v034_does_not_add_an_mcp_sdk_dependency() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    dependencies = tuple(value.casefold() for value in project["dependencies"])

    assert not any(value.startswith(("mcp", "fastmcp")) for value in dependencies)
