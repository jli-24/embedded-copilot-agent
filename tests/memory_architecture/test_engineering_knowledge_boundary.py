from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_knowledge")
FORBIDDEN = (
    "memory_automation",
    "supervisor",
    "agents",
    "workflow",
    "runtime",
    "tool",
    "build",
    "flash",
    "device",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "sqlalchemy",
    "sqlite",
    "openai",
    "anthropic",
    "embedding",
)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return tuple(values)


def test_graph_package_has_no_forbidden_dependencies() -> None:
    for path in PACKAGE.rglob("*.py"):
        for module in _imports(path):
            lowered = module.casefold()
            assert not any(token in lowered for token in FORBIDDEN), path


def test_graph_package_has_no_reverse_writer_or_mutation_dependency() -> None:
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        assert "knowledge_writer" not in source
        assert ".store" not in source
        assert "create_candidate" not in source
        assert "apply_human_approval" not in source
        assert "obsidian" not in source
