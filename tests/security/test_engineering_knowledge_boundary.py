from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_knowledge")


def test_graph_modules_are_not_executors() -> None:
    forbidden_calls = {"open", "exec", "eval", "compile", "system", "run"}
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, path


def test_graph_modules_do_not_import_runtime_or_external_services() -> None:
    forbidden = (
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "sqlalchemy",
        "sqlite",
        "openai",
        "anthropic",
        "embedding",
        "knowledge_writer",
    )
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        assert not any(item in source for item in forbidden), path
