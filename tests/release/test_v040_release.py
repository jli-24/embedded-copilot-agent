from __future__ import annotations

from pathlib import Path

def test_v040_release_history_is_preserved() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/release/v0.40.0.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.40.0" in changelog
    assert "# Embedded Copilot v0.40.0" in release
    assert "Memory Intelligence Layer" in release
    assert "Knowledge Fusion" in release
    assert "Failure-safe Supervisor" in release
    assert "read-side" in release
    assert "## v0.40 Architecture" in readme
    assert "## v0.40 Highlights" in readme
