from __future__ import annotations

import ast
import inspect
from pathlib import Path

from embedded_copilot.context_runtime import (
    EngineeringContextPort,
    EngineeringContextRuntime,
    create_engineering_context_runtime,
)

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
RUNTIME = SRC / "context_runtime"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"
FORBIDDEN_IMPORTS = {
    "fastapi",
    "starlette",
    "streamlit",
    "langgraph",
    "langchain",
    "chromadb",
    "sqlalchemy",
    "sqlite3",
    "shelve",
    "subprocess",
    "pathlib",
    "os",
}
FORBIDDEN_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.model_runtime",
    "embedded_copilot.vision_runtime",
    "embedded_copilot.file_runtime",
    "embedded_copilot.datasheet_runtime",
    "embedded_copilot.rag",
)
FORBIDDEN_OPERATIONS = {
    "write",
    "edit",
    "patch",
    "execute",
    "generate_code",
    "modify",
    "save",
    "persist",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.py")))


def _imports(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_context_runtime_has_framework_independent_boundary() -> None:
    for path in _python_files(RUNTIME):
        tree = _tree(path)
        for module in _imports(tree):
            assert module.split(".", 1)[0] not in FORBIDDEN_IMPORTS, path
            assert not module.startswith(FORBIDDEN_PREFIXES), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {
                    "__import__",
                    "eval",
                    "exec",
                    "compile",
                    "open",
                }, path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_OPERATIONS, path


def test_context_runtime_has_exact_public_exports_and_facade() -> None:
    import embedded_copilot.context_runtime as context_runtime

    assert context_runtime.__all__ == [
        "EngineeringContextPort",
        "EngineeringContextRuntime",
        "create_engineering_context_runtime",
    ]
    assert {
        name
        for name, value in EngineeringContextRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"context_port"}
    assert {
        name
        for name, value in EngineeringContextPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"compose"}
    assert callable(create_engineering_context_runtime)


def test_only_api_main_constructs_context_runtime() -> None:
    callers: list[Path] = []
    for path in _python_files(SRC):
        if path.is_relative_to(RUNTIME):
            continue
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_engineering_context_runtime"
            ):
                callers.append(path)
    assert callers == [CONSTRUCTION_ROOT]


def test_future_coding_agent_receives_no_mutation_capability() -> None:
    assert tuple(inspect.signature(EngineeringContextPort.compose).parameters) == (
        "self",
        "request",
    )
    for forbidden in (*FORBIDDEN_OPERATIONS, "filesystem", "reader", "configuration"):
        assert not hasattr(EngineeringContextPort, forbidden)
