from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.engineering_artifacts as public_package
from embedded_copilot.engineering_artifacts import (
    EngineeringArtifactPort,
    create_engineering_artifact_runtime,
)

ROOT = Path("src/embedded_copilot/engineering_artifacts")


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_package_has_no_io_execution_or_eda_dependencies() -> None:
    forbidden_imports = {
        "asyncio",
        "builtins",
        "ctypes",
        "docker",
        "git",
        "http",
        "importlib",
        "kicad",
        "os",
        "pathlib",
        "serial",
        "shutil",
        "socket",
        "subprocess",
        "threading",
        "urllib",
    }
    forbidden_name_calls = {
        "compile",
        "eval",
        "exec",
        "open",
        "system",
        "write",
    }
    forbidden_attribute_calls = {"open", "system", "write"}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
        assert not forbidden_name_calls.intersection(name_calls), path
        assert not forbidden_attribute_calls.intersection(attribute_calls), path


def test_only_typed_integration_imports_v050_through_v053() -> None:
    protected = (
        "embedded_copilot.engineering_intelligence",
        "embedded_copilot.engineering_hardware",
        "embedded_copilot.engineering_firmware",
        "embedded_copilot.engineering_validation",
    )
    forbidden = (
        "embedded_copilot.engineering_generation",
        "embedded_copilot.execution_runtime",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
    )
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in protected):
            assert "integration" in path.parts, path
        assert not any(value in text for value in forbidden), path


def test_public_boundary_does_not_export_internal_projectors() -> None:
    exports = set(public_package.__all__)
    assert "create_engineering_artifact_runtime" in exports
    assert "EngineeringArtifactPort" in exports
    assert not {"_EngineeringArtifactAgent", "build_report", "project_input"} & exports
    runtime = create_engineering_artifact_runtime()
    assert isinstance(runtime.engineering_artifact_port(), EngineeringArtifactPort)
    assert tuple(
        name
        for name, _ in inspect.getmembers(type(runtime), inspect.isfunction)
        if not name.startswith("_")
    ) == ("engineering_artifact_port",)


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
