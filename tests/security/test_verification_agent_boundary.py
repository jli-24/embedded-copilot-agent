from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.verification_agent as verification
from embedded_copilot.coding_runtime import CodingRuntime
from embedded_copilot.debug_runtime import DebugRuntime
from embedded_copilot.reasoning_runtime import ReasoningRuntime
from embedded_copilot.telemetry_runtime import TelemetryRuntime
from embedded_copilot.tool_runtime import ToolRuntime
from embedded_copilot.vscode_runtime import VSCodeRuntime
from embedded_copilot.workspace_runtime import WorkspaceRuntime

SRC = Path("src/embedded_copilot")
PACKAGE = SRC / "verification_agent"
ROOT_FILES = {
    "__init__.py",
    "agent.py",
    "audit.py",
    "exceptions.py",
    "factory.py",
    "models.py",
    "ports.py",
    "rules.py",
}
CHECK_FILES = {"__init__.py", "firmware.py", "hardware.py", "tool_result.py"}
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
    "embedded_copilot.context_runtime",
    "embedded_copilot.datasheet_runtime",
    "embedded_copilot.file_runtime",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.services",
    "embedded_copilot.tools",
    "embedded_copilot.vscode_runtime",
    "embedded_copilot.workspace_runtime",
)
ALLOWED_RUNTIME_IMPORTS = {
    "embedded_copilot.coding_runtime",
    "embedded_copilot.debug_runtime",
    "embedded_copilot.telemetry_runtime",
    "embedded_copilot.tool_runtime",
}
FORBIDDEN_CALLS = {"__import__", "compile", "eval", "exec", "open"}
FORBIDDEN_ATTRIBUTES = {
    "connect",
    "execute",
    "getenv",
    "now",
    "open",
    "patch",
    "read_bytes",
    "read_text",
    "replace",
    "run",
    "send",
    "sleep",
    "utcnow",
    "write",
    "write_bytes",
    "write_text",
}
FORBIDDEN_METHOD_NAMES = {
    "control",
    "erase",
    "execute",
    "flash",
    "patch",
    "program",
    "reset",
    "run",
    "write",
}
FORBIDDEN_SEMANTICS = {
    "auto_fix",
    "execute_action",
    "fault_confirmed",
    "hardware_broken",
    "root_cause",
}


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def test_verification_agent_is_framework_independent_and_non_executing() -> None:
    assert {path.name for path in PACKAGE.glob("*.py")} == ROOT_FILES
    assert {path.name for path in (PACKAGE / "checks").glob("*.py")} == CHECK_FILES
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            for module in _imported_modules(node):
                assert module.split(".", 1)[0] not in FORBIDDEN_IMPORT_ROOTS, path
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
                if module.startswith(
                    (
                        "embedded_copilot.coding_runtime",
                        "embedded_copilot.debug_runtime",
                        "embedded_copilot.telemetry_runtime",
                        "embedded_copilot.tool_runtime",
                    )
                ):
                    assert module in ALLOWED_RUNTIME_IMPORTS, path
            if isinstance(node, ast.AsyncFunctionDef):
                raise AssertionError(path)
            if isinstance(node, ast.FunctionDef):
                assert node.name not in FORBIDDEN_METHOD_NAMES, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_ATTRIBUTES, path
            if isinstance(node, ast.Attribute):
                assert node.attr not in FORBIDDEN_ATTRIBUTES, path
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                assert not isinstance(
                    statement.value, (ast.Dict, ast.List, ast.Set)
                ), path
        lowered = source.casefold()
        for token in FORBIDDEN_SEMANTICS:
            assert token not in lowered, (path, token)


def test_public_facade_protocols_and_exports_are_narrow() -> None:
    assert {
        name
        for name, value in verification.VerificationAgent.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"verification_port"}
    assert {
        name
        for name, value in verification.VerificationPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"verify"}
    assert {
        name
        for name, value in verification.VerificationCheckerPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"verify"}
    assert isinstance(
        verification.VerificationCheckerPort.__dict__["checker_name"], property
    )
    assert isinstance(
        verification.VerificationCheckerPort.__dict__["supported_subjects"],
        property,
    )
    assert tuple(
        inspect.signature(verification.VerificationPort.verify).parameters
    ) == (
        "self",
        "request",
    )
    for leaked in (
        "CheckerAdapter",
        "CheckerRegistry",
        "aggregate_results",
        "emit_audit",
        "rules",
        "registry",
        "configuration",
    ):
        assert leaked not in verification.__all__


def test_existing_runtime_facades_remain_unchanged() -> None:
    expected = (
        (CodingRuntime, {"coding_port"}),
        (DebugRuntime, {"debug_port"}),
        (TelemetryRuntime, {"telemetry_port"}),
        (ToolRuntime, {"tool_port"}),
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


def test_no_external_production_module_constructs_verification_agent() -> None:
    callers: list[Path] = []
    for path in SRC.rglob("*.py"):
        if path.is_relative_to(PACKAGE):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_verification_agent"
            ):
                callers.append(path)
    assert callers == []
