from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.engineering_firmware as public_package
from embedded_copilot.engineering_firmware import (
    FirmwareEngineeringPort,
    create_engineering_firmware_runtime,
)

ROOT = Path("src/embedded_copilot/engineering_firmware")


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_firmware_runtime_has_no_execution_or_io_dependencies() -> None:
    forbidden_imports = {
        "asyncio",
        "builtins",
        "database",
        "debug_runtime",
        "engineering_generation",
        "execution_runtime",
        "git",
        "http",
        "importlib",
        "network",
        "openocd",
        "os",
        "pathlib",
        "serial",
        "socket",
        "subprocess",
        "tool_runtime",
        "workspace_runtime",
    }
    forbidden_calls = {
        "compile",
        "connect",
        "eval",
        "exec",
        "flash",
        "open",
        "program",
        "reset",
        "run",
        "system",
        "write",
    }
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    tuple(alias.name for alias in node.names)
                    if isinstance(node, ast.Import)
                    else (node.module or "",)
                )
                assert not any(
                    part in forbidden_imports
                    for module in modules
                    for part in module.split(".")
                ), (path, modules)
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                )
                if (
                    name == "compile"
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re"
                ):
                    continue
                assert name not in forbidden_calls, (path, name)


def test_only_integration_imports_protected_public_contracts() -> None:
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if "embedded_copilot.engineering_intelligence" in text or (
            "embedded_copilot.engineering_hardware" in text
        ):
            assert "integration" in path.parts, path


def test_public_boundary_is_facade_contract_and_immutable_dtos_only() -> None:
    exports = set(public_package.__all__)
    assert "create_engineering_firmware_runtime" in exports
    assert "FirmwareEngineeringPort" in exports
    assert (
        not {
            "_FirmwareEngineeringAgent",
            "build_firmware_proposal",
            "project_firmware_input",
        }
        & exports
    )
    runtime = create_engineering_firmware_runtime()
    assert tuple(
        name
        for name, _ in inspect.getmembers(type(runtime), inspect.isfunction)
        if not name.startswith("_")
    ) == ("firmware_engineering_port",)
    assert isinstance(runtime.firmware_engineering_port(), FirmwareEngineeringPort)


def test_typed_boundary_has_no_serialization_round_trip() -> None:
    integration = ROOT / "integration" / "inputs.py"
    tree = ast.parse(integration.read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "model_copy" in calls
    assert "model_validate" in calls
    assert "model_dump" not in calls
    assert "model_dump_json" not in calls
