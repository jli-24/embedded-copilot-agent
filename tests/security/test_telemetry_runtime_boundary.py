from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.telemetry_runtime as telemetry_runtime
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.debug_runtime import DebugRuntime
from embedded_copilot.reasoning_runtime import ReasoningRuntime
from embedded_copilot.vscode_runtime import VSCodeRuntime
from embedded_copilot.workspace_runtime import WorkspaceRuntime

SRC = Path("src/embedded_copilot")
RUNTIME = SRC / "telemetry_runtime"
RUNTIME_FILES = {
    "__init__.py",
    "analysis.py",
    "audit.py",
    "exceptions.py",
    "factory.py",
    "models.py",
    "ports.py",
    "runtime.py",
    "series.py",
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
    "embedded_copilot.coding_runtime",
    "embedded_copilot.file_runtime",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.reasoning_runtime",
    "embedded_copilot.vscode_runtime",
    "embedded_copilot.workspace_runtime",
)
FORBIDDEN_FUNCTION_NAMES = {
    "control",
    "erase",
    "execute",
    "flash",
    "optimize",
    "program",
    "reset",
    "run",
    "serve",
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
FORBIDDEN_ATTRIBUTES = {
    "connect",
    "getenv",
    "iterdir",
    "open",
    "read_bytes",
    "read_text",
    "replace",
    "rglob",
    "scandir",
    "sleep",
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


def test_telemetry_runtime_is_observation_only_and_framework_independent() -> None:
    assert {path.name for path in RUNTIME.glob("*.py")} == RUNTIME_FILES
    for path in RUNTIME.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORT_ROOTS, path
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
                if module.startswith("embedded_copilot.debug_runtime"):
                    assert module == "embedded_copilot.debug_runtime", path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_FUNCTION_NAMES, path
                assert not isinstance(node, ast.AsyncFunctionDef), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_ATTRIBUTES, path
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "utcnow"}, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                assert not isinstance(
                    statement.value, (ast.Dict, ast.List, ast.Set)
                ), path
        for token in (
            "ControlSignalContext",
            "Kp",
            "Ki",
            "Kd",
            "PID",
            "background",
            "persist",
            "filesystem",
        ):
            assert token not in source, (path, token)


def test_public_facade_ports_and_source_contract_are_narrow() -> None:
    assert {
        name
        for name, value in telemetry_runtime.TelemetryRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"telemetry_port"}
    assert {
        name
        for name, value in telemetry_runtime.TelemetryPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"analyze_signal", "collect_sample", "collect_series"}
    assert {
        name
        for name, value in telemetry_runtime.TelemetrySourcePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"read_sample"}
    assert isinstance(
        telemetry_runtime.TelemetrySourcePort.__dict__["source_type"],
        property,
    )
    assert {
        name
        for name, value in telemetry_runtime.TelemetryAuditSink.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"record"}
    assert tuple(
        inspect.signature(telemetry_runtime.create_telemetry_runtime).parameters
    ) == ("sources", "audit_sink")
    for name in {
        "TelemetryAnalyzer",
        "TelemetrySeriesBuilder",
        "TelemetryAuditEmitter",
        "TelemetrySourceAdapter",
        "analyzer",
        "builder",
        "router",
        "registry",
        "cache",
        "database",
    }:
        assert name not in telemetry_runtime.__all__
        assert not hasattr(telemetry_runtime, name)


def test_existing_runtime_contracts_remain_unchanged() -> None:
    expected = (
        (DebugRuntime, {"debug_port"}),
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


def test_no_external_production_module_constructs_telemetry_runtime() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(RUNTIME):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_telemetry_runtime"
            ):
                callers.append(path)

    assert callers == []
