from __future__ import annotations

from pathlib import Path


def test_v033_release_documents_approval_gated_workspace_boundary() -> None:
    release = Path("docs/release/v0.33.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.33.0" in release
    assert "approval-gated" in release
    assert "does not scan directories" in release
    assert "v0.33 Workspace Operation Layer" in architecture
