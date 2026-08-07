from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_context")


def test_context_modules_do_not_import_external_or_runtime_capabilities() -> None:
    forbidden = {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "sqlite3",
        "sqlalchemy",
        "openai",
        "anthropic",
        "embedding",
        "agent",
        "runtime",
        "workflow",
        "tool",
        "build",
        "flash",
        "device",
    }
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.casefold() for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module.casefold()]
            else:
                continue
            assert not any(
                token == module or module.startswith(token + ".")
                for module in modules
                for token in forbidden
            ), path


def test_context_modules_do_not_call_execution_primitives() -> None:
    forbidden = {"open", "exec", "eval", "compile", "system", "run"}
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden, path
