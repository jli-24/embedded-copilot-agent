from __future__ import annotations

import tomllib
from pathlib import Path


def test_v038_release_documents_verification_without_execution() -> None:
    release = Path("docs/release/v0.38.0.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "# Embedded Copilot v0.38.0" in release
    assert "Verification Agent Layer" in release
    assert 'candidate_semantics="unverified"' in release
    assert "FAIL" in release
    assert "不表示已经确认真实设备存在故障" in release
    assert "v0.38 Verification Agent Layer" in architecture
    assert "v0.38.0 新增 Verification Agent Layer" in readme
    assert "## Quality Gate Scope" in release
    assert "staged-change Black gate" in release
    assert "Black 26.5.1" in release
    assert "181 个" in release
    assert "formatting-only" in release
    for non_goal in (
        "Tool execution",
        "Shell",
        "file mutation",
        "hardware control",
        "auto fix",
        "Agent invocation",
    ):
        assert non_goal in release


def test_v038_keeps_dependency_list_unchanged() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert tuple(project["dependencies"]) == (
        "tree-sitter>=0.25,<0.26",
        "tree-sitter-c>=0.24,<0.25",
        "tree-sitter-cpp>=0.23,<0.24",
    )
