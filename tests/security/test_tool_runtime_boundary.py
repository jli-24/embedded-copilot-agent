from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.tool_runtime as tool_runtime
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.debug_runtime import DebugRuntime
from embedded_copilot.reasoning_runtime import ReasoningRuntime
from embedded_copilot.telemetry_runtime import TelemetryRuntime
from embedded_copilot.vscode_runtime import VSCodeRuntime
from embedded_copilot.workspace_runtime import WorkspaceRuntime

SRC = Path("src/embedded_copilot")
RUNTIME = SRC / "tool_runtime"
ROOT_FILES = {
    "__init__.py",
    "audit.py",
    "exceptions.py",
    "executor.py",
    "factory.py",
    "models.py",
    "ports.py",
    "registry.py",
    "runtime.py",
}
ADAPTER_FILES = {"__init__.py", "firmware.py", "serial.py", "test.py"}
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
    "requests",
    "shutil",
    "socket",
    "sqlite3",
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
    "embedded_copilot.file_runtime",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.reasoning_runtime",
    "embedded_copilot.services",
    "embedded_copilot.tools",
    "embedded_copilot.vscode_runtime",
    "embedded_copilot.workspace_runtime",
)
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec", "open"}
FORBIDDEN_ATTRIBUTES = {
    "connect",
    "getenv",
    "open",
    "patch",
    "read_bytes",
    "read_text",
    "replace",
    "run",
    "send",
    "sleep",
    "write",
    "write_bytes",
    "write_text",
}
FORBIDDEN_METHOD_NAMES = {
    "control",
    "erase",
    "flash",
    "patch_file",
    "program",
    "reset",
    "write_file",
}


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def test_tool_runtime_is_framework_independent_and_non_mutating() -> None:
    assert {path.name for path in RUNTIME.glob("*.py")} == ROOT_FILES
    assert {path.name for path in (RUNTIME / "adapters").glob("*.py")} == (
        ADAPTER_FILES
    )
    for path in RUNTIME.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORT_ROOTS, path
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
                if module.startswith("embedded_copilot.debug_runtime"):
                    assert module == "embedded_copilot.debug_runtime", path
            if isinstance(node, ast.AsyncFunctionDef):
                raise AssertionError(path)
            if isinstance(node, ast.FunctionDef):
                assert node.name not in FORBIDDEN_METHOD_NAMES, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_ATTRIBUTES, path
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "utcnow"}, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                assert not isinstance(
                    statement.value,
                    (ast.Dict, ast.List, ast.Set),
                ), path
        lowered = source.casefold()
        for token in (
            "make flash",
            "esptool",
            "openocd",
            "shell=true",
            "workspaceport",
            "firmware binary",
        ):
            assert token not in lowered, (path, token)


def test_public_facade_and_protocols_are_narrow() -> None:
    assert {
        name
        for name, value in tool_runtime.ToolRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"tool_port"}
    assert {
        name
        for name, value in tool_runtime.ToolExecutionPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"execute"}
    assert {
        name
        for name, value in tool_runtime.EngineeringToolPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"execute"}
    assert isinstance(
        tool_runtime.EngineeringToolPort.__dict__["tool_name"],
        property,
    )
    assert tuple(inspect.signature(tool_runtime.create_tool_runtime).parameters) == (
        "tools",
        "permission_port",
        "audit_sink",
    )
    for leaked in (
        "ToolRegistry",
        "ToolExecutor",
        "FirmwareAdapter",
        "SerialAdapter",
        "TestAdapter",
        "registry",
        "executor",
        "adapters",
        "tools",
        "permission",
        "audit",
        "settings",
        "configuration",
    ):
        assert leaked not in tool_runtime.__all__


def test_adapter_package_exports_only_creator_contracts() -> None:
    import embedded_copilot.tool_runtime.adapters as adapters

    assert set(adapters.__all__) == {
        "MockBuildScenario",
        "MockTestScenario",
        "create_mock_firmware_build_adapter",
        "create_mock_firmware_test_adapter",
        "create_serial_log_adapter",
    }


def test_existing_runtime_contracts_remain_unchanged() -> None:
    expected = (
        (DebugRuntime, {"debug_port"}),
        (TelemetryRuntime, {"telemetry_port"}),
        (CodingRuntime, {"coding_port"}),
        (WorkspaceRuntime, {"workspace_port"}),
        (VSCodeRuntime, {"vscode_port"}),
        (ReasoningRuntime, {"reasoning_port"}),
    )
    for runtime_type, methods in expected:
        assert {
            name
            for name, value in runtime_type.__dict__.items()
            if callable(value) and not name.startswith("_")
        } == methods


def test_no_external_production_module_constructs_tool_runtime() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(RUNTIME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_tool_runtime"
            ):
                callers.append(path)
    assert callers == []
