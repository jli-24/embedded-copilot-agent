from __future__ import annotations

import ast
from pathlib import Path


PACKAGE = Path(__file__).parents[2] / "src" / "embedded_copilot" / "knowledge_writer"
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.conversation",
    "embedded_copilot.conversation_memory",
    "embedded_copilot.memory_automation.application",
    "embedded_copilot.memory_automation.factory",
    "embedded_copilot.memory_automation.projector",
    "embedded_copilot.memory_automation.promotion",
    "embedded_copilot.memory_automation.service",
    "embedded_copilot.knowledge_evolution",
    "embedded_copilot.services.canonical_runtime",
    "embedded_copilot.services.legacy_runtime",
)
FORBIDDEN_CALLS = {
    "create_candidate",
    "promote",
    "apply_human_approval",
    "add_relation",
    "update_node",
    "mutate_graph",
    "read_text",
    "read_bytes",
    "glob",
    "rglob",
    "iterdir",
}


def _imports(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)


def test_writer_consumes_approved_projection_only() -> None:
    contracts = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
    writer = (PACKAGE / "writer.py").read_text(encoding="utf-8")

    assert "write_approved_projection" in contracts
    assert "write_approved_graph_projection" in contracts
    assert "write_approved_projection" in writer
    assert "write_approved_graph_projection" in writer


def test_writer_has_no_reverse_knowledge_or_runtime_imports() -> None:
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = _imports(tree)
        assert not any(
            module == prefix or module.startswith(f"{prefix}.")
            for module in imports
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ), path


def test_writer_has_no_candidate_input_surface() -> None:
    contracts = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
    writer = (PACKAGE / "writer.py").read_text(encoding="utf-8")
    compatibility = (PACKAGE / "_legacy_candidate_compat.py").read_text(
        encoding="utf-8"
    )

    assert "MemoryCandidate" not in contracts
    assert "artifact_from_candidate" not in contracts
    assert "MemoryCandidate" not in writer
    assert "artifact_from_candidate" not in writer
    assert "artifact_from_candidate" in compatibility


def test_writer_does_not_parse_markdown_or_mutate_knowledge() -> None:
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else None
                )
                assert function_name not in FORBIDDEN_CALLS, (path, function_name)
