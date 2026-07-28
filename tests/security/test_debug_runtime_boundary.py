from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.debug_runtime as debug_runtime
import embedded_copilot.debug_runtime.adapters as debug_adapters
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.reasoning_runtime import ReasoningRuntime
from embedded_copilot.vscode_runtime import VSCodeRuntime
from embedded_copilot.workspace_runtime import WorkspaceRuntime

SRC = Path("src/embedded_copilot")
RUNTIME = SRC / "debug_runtime"
ROOT_FILES = {
    "__init__.py",
    "audit.py",
    "exceptions.py",
    "models.py",
    "ports.py",
    "runtime.py",
    "snapshot.py",
    "telemetry.py",
}
ADAPTER_FILES = {
    "__init__.py",
    "base.py",
    "gdb.py",
    "jlink.py",
    "stlink.py",
    "uart.py",
}
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "anthropic",
    "asyncio",
    "chromadb",
    "fastapi",
    "httpx",
    "langgraph",
    "multiprocessing",
    "openai",
    "os",
    "pathlib",
    "pyocd",
    "pylink",
    "requests",
    "serial",
    "shutil",
    "socket",
    "starlette",
    "streamlit",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "time",
    "urllib",
    "uuid",
    "websockets",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.api",
    "embedded_copilot.debug.",
    "embedded_copilot.hardware",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.reasoning_runtime",
)
FORBIDDEN_FUNCTION_NAMES = {
    "breakpoint",
    "close",
    "connect",
    "continue_target",
    "erase",
    "execute",
    "flash",
    "loadfile",
    "open",
    "program",
    "reset",
    "run",
    "send",
    "serve",
    "step",
    "write",
    "write_file",
    "write_memory",
    "write_register",
}
FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
}
FORBIDDEN_ATTRIBUTES = {
    "connect",
    "iterdir",
    "model_copy",
    "open",
    "read_bytes",
    "read_text",
    "replace",
    "rglob",
    "scandir",
    "unlink",
    "walk",
    "write_bytes",
    "write_text",
}


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def test_debug_runtime_is_observation_only_and_framework_independent() -> None:
    assert {path.name for path in RUNTIME.glob("*.py")} == ROOT_FILES
    assert {path.name for path in (RUNTIME / "adapters").glob("*.py")} == ADAPTER_FILES
    for path in RUNTIME.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORT_ROOTS, path
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_FUNCTION_NAMES, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_ATTRIBUTES, path
                assert node.func.attr not in {
                    "erase",
                    "loadfile",
                    "program",
                    "reset",
                    "send",
                    "write_memory",
                    "write_register",
                }, path
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "utcnow"}, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                value = statement.value
                assert not isinstance(value, (ast.Dict, ast.List, ast.Set)), path


def test_public_facade_ports_and_source_contract_are_narrow() -> None:
    assert {
        name
        for name, value in debug_runtime.DebugRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"debug_port"}
    assert {
        name
        for name, value in debug_runtime.DebugPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"collect_snapshot", "collect_telemetry", "identify_target"}
    assert {
        name
        for name, value in debug_runtime.DebugSourcePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"read_identity", "read_snapshot", "read_telemetry"}
    assert isinstance(
        debug_runtime.DebugSourcePort.__dict__["source_type"],
        property,
    )
    assert {
        name
        for name, value in debug_runtime.DebugAuditSink.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"record"}
    assert tuple(inspect.signature(debug_runtime.create_debug_runtime).parameters) == (
        "sources",
        "audit_sink",
    )
    for name in {
        "ReadOnlyDebugAdapter",
        "UARTDebugAdapter",
        "JLinkDebugAdapter",
        "STLinkDebugAdapter",
        "GDBDebugAdapter",
        "router",
        "registry",
        "connection",
        "handle",
        "process",
    }:
        assert name not in debug_runtime.__all__
        assert not hasattr(debug_adapters, name)


def test_existing_runtime_contracts_remain_unchanged() -> None:
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
    assert {
        name
        for name, value in VSCodeRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"vscode_port"}
    assert {
        name
        for name, value in ReasoningRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"reasoning_port"}


def test_no_external_production_module_constructs_debug_runtime() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(RUNTIME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_debug_runtime"
            ):
                callers.append(path)

    assert callers == []
