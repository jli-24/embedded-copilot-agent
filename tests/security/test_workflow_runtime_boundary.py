from __future__ import annotations

import ast
from pathlib import Path

import embedded_copilot.workflow_runtime as public

ROOT = Path("src/embedded_copilot/workflow_runtime")


def _modules() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple(
        (path, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(ROOT.rglob("*.py"))
    )


def test_workflow_runtime_has_no_forbidden_dependencies() -> None:
    forbidden_roots = {
        "langgraph",
        "fastapi",
        "starlette",
        "streamlit",
        "subprocess",
        "socket",
        "httpx",
        "requests",
        "sqlalchemy",
    }
    forbidden_embedded = (
        "embedded_copilot.supervisor",
        "embedded_copilot.agents",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_memory",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "embedded_copilot.debug_runtime",
    )
    for path, tree in _modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            assert not any(
                name.split(".", 1)[0] in forbidden_roots for name in names
            ), path
            assert not any(
                name.startswith(prefix)
                for name in names
                for prefix in forbidden_embedded
            ), path


def test_workflow_runtime_has_no_execution_or_mutation_calls() -> None:
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "system",
        "popen",
        "run",
        "write",
        "write_text",
        "write_bytes",
        "replace",
        "unlink",
        "sleep",
        "uuid4",
        "now",
        "utcnow",
    }
    for path, tree in _modules():
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        calls.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        )
        assert calls.isdisjoint(forbidden_calls), path


def test_public_package_does_not_export_internal_implementations() -> None:
    for name in (
        "build_task_dag",
        "build_schedule",
        "project_workflow_risks",
        "validate_workflow_approval",
        "_EngineeringWorkflowService",
    ):
        assert not hasattr(public, name)


def test_scheduler_module_cannot_observe_risk_projection() -> None:
    source = (ROOT / "scheduler" / "service.py").read_text(encoding="utf-8")
    assert "WorkflowRisk" not in source
    assert "risk" not in source.casefold()
