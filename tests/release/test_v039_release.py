from pathlib import Path

import tomllib


def test_v039_release_documents_security_and_quality_scope() -> None:
    text = Path("docs/release/v0.39.0.md").read_text(encoding="utf-8")
    for phrase in (
        "contract-first",
        "InMemory",
        "CANDIDATE",
        "VERIFIED",
        "Workspace Runtime",
        "Black 26.5.1",
        "181",
        "no hard delete",
    ):
        assert phrase in text
    for non_goal in (
        "real persistence",
        "Agent",
        "LLM",
        "RAG",
        "Tool execution",
        "hardware operation",
    ):
        assert non_goal in text


def test_v039_keeps_dependency_list_unchanged() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    assert tuple(project["dependencies"]) == (
        "tree-sitter>=0.25,<0.26",
        "tree-sitter-c>=0.24,<0.25",
        "tree-sitter-cpp>=0.23,<0.24",
    )
