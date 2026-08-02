from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("src/embedded_copilot/web_api")


def _dev_files() -> tuple[Path, ...]:
    return tuple(sorted((*ROOT.joinpath("dev").rglob("*.py"), ROOT / "dev_server.py")))


def test_demo_adapter_has_no_external_or_execution_dependencies() -> None:
    forbidden_roots = {
        "embedded_copilot.agent_execution",
        "embedded_copilot.engineering_execution",
        "embedded_copilot.execution_runtime",
        "embedded_copilot.supervisor",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "subprocess",
        "pathlib",
        "os",
        "socket",
        "requests",
        "httpx",
        "sqlalchemy",
        "serial",
    }
    for path in _dev_files():
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
            for root in forbidden_roots
        ), path


def test_demo_adapter_contains_no_io_execution_or_persistence_calls() -> None:
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "compile",
        "system",
        "Popen",
        "run",
        "build",
        "flash",
        "debug",
        "connect",
        "write",
    }
    for path in _dev_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert names.isdisjoint(forbidden_calls), path
        assert attributes.isdisjoint(forbidden_calls - {"compile"}), path


def test_demo_state_is_only_the_injected_repository_instance() -> None:
    from embedded_copilot.web_api.dev import (
        DemoAttachmentProjectionPort,
        DemoPreparationPort,
        DemoProductWorkspacePort,
        InMemoryWebProjectRepository,
    )

    assert DemoPreparationPort.__slots__ == ()
    assert DemoProductWorkspacePort.__slots__ == ()
    assert DemoAttachmentProjectionPort.__slots__ == ()
    assert InMemoryWebProjectRepository.__slots__ == ("_items",)
    assert not hasattr(InMemoryWebProjectRepository, "items")
