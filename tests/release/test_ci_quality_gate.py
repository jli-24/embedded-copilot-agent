from __future__ import annotations

from pathlib import Path


def test_quality_workflow_runs_all_offline_release_gates() -> None:
    workflow = Path(".github/workflows/quality.yml").read_text(encoding="utf-8")

    assert "python-version: \"3.11\"" in workflow
    assert "pytest tests/release/test_contract_compatibility.py -q" in workflow
    assert "pytest -q" in workflow
    assert "python -m compileall -q src tests" in workflow
    assert "ruff check ." in workflow
    assert "services:" not in workflow
    assert "secrets." not in workflow
    assert "docker login" not in workflow
