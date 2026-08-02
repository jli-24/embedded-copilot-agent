from __future__ import annotations

import ast
from pathlib import Path

AI_ROOT = Path("src/embedded_copilot/ai_runtime")
FEEDBACK_ROOT = Path("src/embedded_copilot/conversation_feedback")
EVENT_ROOT = Path("src/embedded_copilot/engineering_events")


def _files() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                *AI_ROOT.rglob("*.py"),
                *FEEDBACK_ROOT.rglob("*.py"),
                *EVENT_ROOT.rglob("*.py"),
            )
        )
    )


def test_ai_feedback_and_event_layers_have_no_io_or_execution_dependencies() -> None:
    forbidden = {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "sqlalchemy",
        "chromadb",
        "openai",
        "serial",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "embedded_copilot.engineering_execution",
        "embedded_copilot.supervisor",
    }
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert not any(
            imported == root or imported.startswith(f"{root}.")
            for imported in imports
            for root in forbidden
        ), path
        for imported in imports:
            if imported.startswith("embedded_copilot.knowledge"):
                assert path.as_posix().endswith("integration/knowledge.py")


def test_ai_feedback_and_event_layers_have_no_control_or_persistence_calls() -> None:
    forbidden = {
        "open",
        "exec",
        "eval",
        "system",
        "Popen",
        "write",
        "build",
        "flash",
        "debug",
        "commit",
        "save",
    }
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert calls.isdisjoint(forbidden), path
        source = path.read_text(encoding="utf-8").lower()
        assert "api_key=" not in source
        assert "traceback" not in source

