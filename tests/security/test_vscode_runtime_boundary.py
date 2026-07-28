from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import embedded_copilot.vscode_runtime as vscode_runtime
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.workspace_runtime import WorkspaceRuntime
from pydantic import BaseModel

SRC = Path("src/embedded_copilot")
RUNTIME = SRC / "vscode_runtime"
EXPECTED_FILES = {
    "__init__.py",
    "context.py",
    "errors.py",
    "facade.py",
    "mcp_server.py",
    "models.py",
    "ports.py",
    "runtime.py",
    "tools.py",
}
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "aiohttp",
    "anthropic",
    "chromadb",
    "fastapi",
    "fastmcp",
    "httpx",
    "langgraph",
    "mcp",
    "multiprocessing",
    "openai",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "ssl",
    "starlette",
    "streamlit",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "urllib",
    "websockets",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.api",
    "embedded_copilot.file_runtime",
    "embedded_copilot.hardware",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.reasoning_runtime",
    "embedded_copilot.vision_runtime",
)
FORBIDDEN_PUBLIC_OPERATIONS = {
    "build",
    "commit",
    "execute",
    "execute_command",
    "flash",
    "git_commit",
    "main",
    "open",
    "patch",
    "patch_file",
    "run",
    "serve",
    "shell",
    "write",
    "write_file",
}
FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
}


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def test_vscode_runtime_is_transport_and_filesystem_independent() -> None:
    assert {path.name for path in RUNTIME.glob("*.py")} == EXPECTED_FILES
    for path in RUNTIME.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORT_ROOTS, path
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    assert node.name not in FORBIDDEN_PUBLIC_OPERATIONS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "connect",
                    "iterdir",
                    "listen",
                    "read_bytes",
                    "read_text",
                    "replace",
                    "rglob",
                    "scandir",
                    "unlink",
                    "walk",
                    "write_bytes",
                    "write_text",
                }, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                assert not isinstance(value, (ast.Dict, ast.List, ast.Set)), path


def test_mcp_module_is_adapter_only_and_has_no_server_entrypoint() -> None:
    path = RUNTIME / "mcp_server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    assert not any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and any(
            isinstance(item, ast.Constant) and item.value == "__main__"
            for item in node.test.comparators
        )
        for node in ast.walk(tree)
    )
    assert {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    } == set()


def test_public_facade_and_ports_do_not_expose_internal_ownership() -> None:
    assert set(vscode_runtime.__all__) == {
        "ChangeProposalResult",
        "DEFAULT_CAPABILITIES",
        "MCPToolAdapter",
        "MCPToolName",
        "MCPToolResult",
        "VSCodeCapability",
        "VSCodeCapabilityUnavailable",
        "VSCodePort",
        "VSCodeRuntime",
        "create_vscode_runtime",
    }
    assert {
        name
        for name, value in vscode_runtime.VSCodeRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"vscode_port"}
    assert {
        name
        for name, value in vscode_runtime.VSCodePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {
        "analyze_build",
        "analyze_code",
        "apply_approved_change",
        "create_change_proposal",
        "inspect_context",
        "review_diff",
    }
    for name in {
        "capabilities",
        "coding_port",
        "mcp_adapter",
        "registry",
        "tools",
        "validator",
        "workspace_port",
        "writer",
    }:
        assert name not in vscode_runtime.__all__


def test_all_vscode_dtos_are_frozen_and_extra_forbid() -> None:
    models = importlib.import_module("embedded_copilot.vscode_runtime.models")
    contracts = tuple(
        value
        for value in vars(models).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == models.__name__
        and not value.__name__.startswith("_")
    )

    assert {value.__name__ for value in contracts} == {
        "ApprovedChangeRequest",
        "ChangeProposalResult",
        "MCPToolResult",
    }
    for contract in contracts:
        assert contract.model_config["extra"] == "forbid"
        assert contract.model_config["frozen"] is True
        assert contract.model_config["revalidate_instances"] == "always"


def test_existing_runtime_boundaries_remain_unchanged() -> None:
    assert {
        name
        for name, value in CodingRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"coding_port"}
    assert {
        name
        for name, value in WorkspaceRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"workspace_port"}


def test_no_external_production_module_constructs_vscode_runtime() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(RUNTIME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_vscode_runtime"
            ):
                callers.append(path)

    assert callers == []


def test_protocol_signatures_remain_synchronous() -> None:
    for method_name in (
        "inspect_context",
        "analyze_code",
        "analyze_build",
        "review_diff",
        "create_change_proposal",
        "apply_approved_change",
    ):
        method = getattr(vscode_runtime.VSCodePort, method_name)
        assert not inspect.iscoroutinefunction(method)
