from __future__ import annotations

import ast
from pathlib import Path

RUNTIME_ROOT = Path("src/embedded_copilot/coding_runtime")
FORBIDDEN_IMPORT_ROOTS = {
    "agents",
    "api",
    "model_runtime",
    "rag",
    "streamlit",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "os",
    "pathlib",
    "random",
    "datetime",
    "uuid",
}
FORBIDDEN_CAPABILITIES = {"write", "patch", "apply", "execute", "generate", "commit"}


def _imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_coding_runtime_has_no_external_or_mutating_dependencies() -> None:
    for path in RUNTIME_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = _imports(tree)
        assert not imports & FORBIDDEN_IMPORT_ROOTS, path
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                assert node.name not in FORBIDDEN_CAPABILITIES, f"{path}: {node.name}"


def test_coding_runtime_does_not_use_dynamic_import_or_mutable_module_state() -> None:
    for path in RUNTIME_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec"}, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = (
                    statement.value
                    if isinstance(statement, ast.AnnAssign)
                    else statement.value
                )
                assert not isinstance(value, (ast.Dict, ast.List, ast.Set)), path
