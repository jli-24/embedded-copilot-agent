from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.engineering_validation as public_package
from embedded_copilot.engineering_validation import (
    HardwareValidationPort,
    create_hardware_validation_runtime,
)

from tests.engineering_validation.conftest import FakeEvidencePort

ROOT = Path("src/embedded_copilot/engineering_validation")


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_validation_runtime_has_no_io_execution_or_hardware_dependencies() -> None:
    forbidden_imports = {
        "asyncio",
        "database",
        "debug_runtime",
        "execution_runtime",
        "git",
        "hardware_intelligence",
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


def test_only_integration_imports_engineering_input_contracts() -> None:
    protected = (
        "embedded_copilot.engineering_firmware",
        "embedded_copilot.engineering_hardware",
        "embedded_copilot.engineering_intelligence",
    )
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if any(item in text for item in protected):
            assert "integration" in path.parts, path


def test_public_boundary_is_facade_ports_and_immutable_dtos_only() -> None:
    exports = set(public_package.__all__)
    assert "create_hardware_validation_runtime" in exports
    assert "HardwareValidationPort" in exports
    assert "DeviceEvidencePort" in exports
    assert (
        not {
            "_HardwareValidationAgent",
            "build_validation_report",
            "project_validation_input",
        }
        & exports
    )
    runtime = create_hardware_validation_runtime(evidence_port=FakeEvidencePort())
    assert tuple(
        name
        for name, _ in inspect.getmembers(type(runtime), inspect.isfunction)
        if not name.startswith("_")
    ) == ("hardware_validation_port",)
    assert isinstance(runtime.hardware_validation_port(), HardwareValidationPort)


def test_typed_integration_has_no_serialization_round_trip() -> None:
    tree = ast.parse((ROOT / "integration" / "inputs.py").read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "model_copy" in calls
    assert "model_validate" in calls
    assert "model_dump" not in calls
    assert "model_dump_json" not in calls
