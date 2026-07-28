from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import embedded_copilot.workspace_runtime as workspace_runtime
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.file_runtime import FileRuntime
from embedded_copilot.workspace_runtime import WorkspacePort, WorkspaceRuntime

SRC = Path("src/embedded_copilot")
RUNTIME = Path("src/embedded_copilot/workspace_runtime")
FORBIDDEN_IMPORTS = {
    "agents",
    "api",
    "anthropic",
    "chromadb",
    "fastapi",
    "git",
    "langgraph",
    "model_runtime",
    "intelligence",
    "openai",
    "rag",
    "starlette",
    "streamlit",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "tempfile",
    "logging",
    "random",
    "time",
    "uuid",
}
FORBIDDEN_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.api",
    "embedded_copilot.coding_runtime",
    "embedded_copilot.experience",
    "embedded_copilot.file_runtime",
    "embedded_copilot.intelligence",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.vision_runtime",
)
FORBIDDEN_OPERATIONS = {"generate", "execute", "commit", "push", "shell"}
FORBIDDEN_FILESYSTEM_CALLS = {"glob", "iterdir", "rglob", "scandir", "walk"}


def test_workspace_runtime_static_boundary() -> None:
    for path in RUNTIME.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                modules = ()
            for module in modules:
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORTS, path
                assert not module.startswith(FORBIDDEN_PREFIXES), path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_OPERATIONS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {
                    "__import__",
                    "eval",
                    "exec",
                    "compile",
                }, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_FILESYSTEM_CALLS, path
                assert not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr
                    in {"getenv", "putenv", "popen", "spawnl", "spawnv", "system"}
                ), path
            if isinstance(node, ast.Attribute):
                assert not (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                    and node.attr == "environ"
                ), path


def test_workspace_writer_protocol_is_private() -> None:
    ports = importlib.import_module("embedded_copilot.workspace_runtime.ports")

    assert not hasattr(ports, "FileWritePort")


def test_workspace_public_contract_and_facade_are_narrow() -> None:
    assert set(workspace_runtime.__all__) == {
        "ApprovalContext",
        "ApprovalStatus",
        "ApplyResult",
        "ApplyStatus",
        "ChangeOperation",
        "ChangeProposal",
        "FrozenWorkspaceSnapshot",
        "ValidationResult",
        "ValidationStatus",
        "WorkspaceAuditEvent",
        "WorkspaceFileSummary",
        "WorkspaceInspectionRequest",
        "WorkspaceLanguage",
        "WorkspacePort",
        "WorkspaceRuntime",
        "create_workspace_runtime",
    }
    assert {
        name
        for name, value in WorkspacePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"inspect_workspace", "validate_change", "apply_change"}
    assert tuple(inspect.signature(WorkspacePort.inspect_workspace).parameters) == (
        "self",
        "request",
    )
    assert tuple(inspect.signature(WorkspacePort.validate_change).parameters) == (
        "self",
        "proposal",
    )
    assert tuple(inspect.signature(WorkspacePort.apply_change).parameters) == (
        "self",
        "proposal",
        "approval",
    )
    assert {
        name
        for name, value in WorkspaceRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"workspace_port"}
    for internal in {
        "audit",
        "configuration",
        "filesystem",
        "root",
        "settings",
        "validator",
        "writer",
    }:
        assert internal not in workspace_runtime.__all__


def test_workspace_runtime_has_no_production_composition_consumer() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(RUNTIME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_workspace_runtime"
            ):
                callers.append(path)

    assert callers == []


def test_coding_runtime_remains_workspace_independent_and_read_only() -> None:
    coding_runtime = SRC / "coding_runtime"
    for path in coding_runtime.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                modules = ()
            assert not any(
                module.startswith("embedded_copilot.workspace_runtime")
                for module in modules
            ), path
    assert {
        name
        for name, value in CodingRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"coding_port"}


def test_file_runtime_remains_workspace_independent_and_read_only() -> None:
    file_runtime = SRC / "file_runtime"
    for path in file_runtime.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                modules = ()
            assert not any(
                module.startswith("embedded_copilot.workspace_runtime")
                for module in modules
            ), path
    public_methods = {
        name
        for name, value in FileRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    }
    assert "file_port" in public_methods
    assert not public_methods.intersection(
        {
            "apply_change",
            "execute",
            "filesystem",
            "patch",
            "workspace_port",
            "write",
        }
    )
