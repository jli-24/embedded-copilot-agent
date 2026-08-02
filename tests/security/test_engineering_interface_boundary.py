from __future__ import annotations

import ast
from pathlib import Path

import embedded_copilot.engineering_interface as public

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "engineering_interface"


def _modules() -> dict[Path, ast.Module]:
    return {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in PACKAGE.rglob("*.py")
    }


def test_engineering_interface_has_no_framework_or_execution_dependencies() -> None:
    forbidden = {
        "fastapi",
        "starlette",
        "streamlit",
        "gradio",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "pathlib",
        "os",
        "threading",
        "asyncio",
        "sqlite3",
        "sqlalchemy",
        "agent_execution",
        "execution_runtime",
        "tool_runtime",
        "workspace_runtime",
        "engineering_memory",
    }
    for path, tree in _modules().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0], node.module}
            else:
                continue
            assert not any(
                token in name for token in forbidden for name in names
            ), f"forbidden import in {path}: {sorted(names)}"


def test_existing_runtime_imports_are_limited_to_public_integration_modules() -> None:
    for path, tree in _modules().items():
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module.startswith("embedded_copilot.workflow_runtime"):
                assert relative == "integration/workflow.py"
                assert node.module == "embedded_copilot.workflow_runtime"
            if node.module.startswith("embedded_copilot.human_loop"):
                assert relative == "integration/human_loop.py"
                assert node.module == "embedded_copilot.human_loop"


def test_package_has_no_io_background_or_serialization_round_trip() -> None:
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "__import__",
        "model_dump_json",
        "loads",
        "load",
        "write",
        "read",
        "send",
        "run",
        "start",
        "connect",
    }
    for path, tree in _modules().items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            assert name not in forbidden_calls, f"forbidden call in {path}: {name}"


def test_public_facade_does_not_expose_internal_capabilities() -> None:
    runtime = public.EngineeringInterfaceRuntime
    assert set(name for name in vars(runtime) if not name.startswith("_")) == {
        "engineering_interface_port"
    }
    for forbidden in (
        "workflow_port",
        "human_loop_port",
        "settings",
        "config",
        "session_store",
        "repository",
        "filesystem",
    ):
        assert not hasattr(runtime, forbidden)
