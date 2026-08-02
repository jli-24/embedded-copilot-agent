from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("src/embedded_copilot/web_api")


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_web_api_has_no_forbidden_runtime_or_execution_dependencies() -> None:
    forbidden_roots = {
        "embedded_copilot.engineering_hardware",
        "embedded_copilot.engineering_firmware",
        "embedded_copilot.engineering_execution",
        "embedded_copilot.engineering_artifacts",
        "embedded_copilot.engineering_validation",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "sqlalchemy",
    }
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            imported == root or imported.startswith(f"{root}.")
            for imported in imports
            for root in forbidden_roots
        ), path
        for imported in imports:
            if imported.startswith("embedded_copilot.product"):
                assert "integration" in path.parts
            if imported.startswith("embedded_copilot.engineering_interface"):
                assert "integration" in path.parts


def test_web_layer_contains_no_storage_or_execution_implementation() -> None:
    forbidden_name_calls = {
        "open",
        "exec",
        "eval",
        "compile",
        "system",
        "Popen",
        "run",
        "build",
        "flash",
        "debug",
    }
    forbidden_attribute_calls = forbidden_name_calls - {"compile"}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        name_calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attribute_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert name_calls.isdisjoint(forbidden_name_calls), path
        assert attribute_calls.isdisjoint(forbidden_attribute_calls), path
        text = path.read_text(encoding="utf-8").lower()
        assert "traceback" not in text
        assert "raw_log" not in text
