from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.engineering_execution as public_package
from embedded_copilot.engineering_execution import (
    EngineeringExecutionPort,
    create_engineering_execution_runtime,
)

ROOT = Path("src/embedded_copilot/engineering_execution")


def _files() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_package_has_no_real_execution_or_external_dependencies() -> None:
    forbidden_imports = {
        "asyncio",
        "builtins",
        "ctypes",
        "docker",
        "git",
        "http",
        "importlib",
        "os",
        "pathlib",
        "serial",
        "shutil",
        "socket",
        "subprocess",
        "threading",
        "urllib",
    }
    forbidden_names = {"compile", "eval", "exec", "open", "write"}
    forbidden_attributes = {"connect", "open", "run", "system", "write"}
    forbidden_text = (
        "idf.py",
        "openocd",
        "jtag",
        "swd",
        "kicad",
        "hardware_sdk",
        "device_control",
    )
    for path in _files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
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
        assert not forbidden_imports.intersection(imports), path
        assert not forbidden_names.intersection(name_calls), path
        assert not forbidden_attributes.intersection(attribute_calls), path
        assert not any(token in source.casefold() for token in forbidden_text), path


def test_only_integration_imports_v053_and_v054_public_contracts() -> None:
    protected = (
        "embedded_copilot.engineering_artifacts",
        "embedded_copilot.engineering_validation",
    )
    forbidden = (
        "embedded_copilot.execution_runtime",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "embedded_copilot.supervisor",
        "embedded_copilot.engineering_memory",
    )
    for path in _files():
        source = path.read_text(encoding="utf-8")
        if any(value in source for value in protected):
            assert "integration" in path.parts, path
        assert not any(value in source for value in forbidden), path


def test_typed_integration_has_no_serialization_round_trip() -> None:
    for path in (ROOT / "integration").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "model_copy" in calls or path.name == "__init__.py"
        assert "model_validate" in calls or path.name == "__init__.py"
        assert "model_dump" not in calls
        assert "model_dump_json" not in calls


def test_root_exports_only_public_contract_surface() -> None:
    exports = set(public_package.__all__)
    assert "create_engineering_execution_runtime" in exports
    assert "EngineeringExecutionPort" in exports
    assert (
        not {"_EngineeringExecutionService", "build_report", "project_request"}
        & exports
    )
    runtime = create_engineering_execution_runtime()
    assert isinstance(runtime.engineering_execution_port(), EngineeringExecutionPort)
    assert tuple(
        name
        for name, _ in inspect.getmembers(type(runtime), inspect.isfunction)
        if not name.startswith("_")
    ) == ("engineering_execution_port",)
