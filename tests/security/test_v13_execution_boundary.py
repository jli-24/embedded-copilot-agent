from __future__ import annotations

import ast
from pathlib import Path

from tests.execution.test_build_execution import _request

ROOTS = (
    Path("src/embedded_copilot/firmware_agent"),
    Path("src/embedded_copilot/execution"),
    Path("src/embedded_copilot/engineering_observation"),
)
FORBIDDEN_IMPORTS = {
    "aiohttp",
    "docker",
    "git",
    "httpx",
    "os",
    "pathlib",
    "requests",
    "serial",
    "shutil",
    "socket",
    "subprocess",
}


def test_v13_packages_do_not_import_external_execution_capabilities() -> None:
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert imports.isdisjoint(FORBIDDEN_IMPORTS), path


def test_production_has_no_concrete_build_adapter_or_direct_process_call() -> None:
    adapter_files = tuple(
        path
        for path in Path("src/embedded_copilot/execution/adapters").rglob("*.py")
        if path.name != "__init__.py"
    )
    assert adapter_files == ()

    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert calls.isdisjoint(
            {"system", "run", "Popen", "write_text", "write_bytes"}
        ), path


def test_build_request_serialization_contains_no_host_secret_fields() -> None:
    serialized = _request().model_dump_json().lower()

    for forbidden in (
        "environment",
        "stdout",
        "stderr",
        "binary_path",
        "working_directory",
        "token",
        "credential",
    ):
        assert forbidden not in serialized


def test_web_boundary_does_not_self_sign_build_approval() -> None:
    path = Path("src/embedded_copilot/web_api/service.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    service = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "start_build"
    )
    called_names = {
        node.func.id
        for node in ast.walk(service)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(service)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "BuildApproval" not in called_names
    assert "resolve" in called_attributes


def _python_files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for root in ROOTS
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )
