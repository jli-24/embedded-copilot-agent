from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_context")


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return tuple(values)


def test_context_engine_has_only_projection_dependencies() -> None:
    forbidden = (
        "engineering_memory",
        "memory_automation",
        "approval",
        "agents",
        "supervisor",
        "runtime",
        "workflow",
        "tool",
        "build",
        "flash",
        "device",
        "autonomous_loop",
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
    for path in PACKAGE.rglob("*.py"):
        imports = tuple(value.casefold() for value in _imports(path))
        assert not any(
            token in module for module in imports for token in forbidden
        ), path


def test_context_engine_has_no_reverse_or_execution_surface() -> None:
    forbidden_text = (
        "create_candidate",
        "apply_human_approval",
        "knowledge_writer",
        "obsidian",
        "open(",
        "exec(",
        "eval(",
        "subprocess",
        "socket",
    )
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        assert not any(token in source for token in forbidden_text), path
