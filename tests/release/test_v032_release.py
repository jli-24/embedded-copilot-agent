from __future__ import annotations

from pathlib import Path


def test_v032_release_note_and_readme_document_coding_runtime_boundaries() -> None:
    release = Path("docs/release/v0.32.0.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.32.0" in release
    assert "CodingIntelligencePort" in release
    assert "does not write code" in release
    assert "hardware/software conflict as verified" in release
    assert "Coding Runtime" in readme
    assert "不执行构建或 Git" in readme
