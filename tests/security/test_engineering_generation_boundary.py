from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("src/embedded_copilot/engineering_generation")


def _modules() -> tuple[Path, ...]:
    return tuple(sorted(ROOT.rglob("*.py")))


def test_engineering_generation_has_no_forbidden_dependencies() -> None:
    forbidden = (
        "embedded_copilot.supervisor",
        "embedded_copilot.agents",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_memory",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "langgraph",
        "subprocess",
        "socket",
        "httpx",
        "requests",
        "sqlite3",
    )
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            assert not any(
                name == blocked or name.startswith(blocked + ".")
                for name in names
                for blocked in forbidden
            ), path


def test_only_integration_imports_public_v043_and_workflow_contracts() -> None:
    importers = []
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        if (
            "embedded_copilot.agent_execution" in source
            or "embedded_copilot.workflow_runtime" in source
        ):
            importers.append(path.relative_to(ROOT).as_posix())
            assert "embedded_copilot.agent_execution.models" not in source
            assert "embedded_copilot.agent_execution.runtime" not in source
            assert "embedded_copilot.workflow_runtime.models" not in source
            assert "embedded_copilot.workflow_runtime.runtime" not in source
    assert importers == ["integration/projection.py"]


def test_runtime_has_no_mutation_or_execution_escape_hatches() -> None:
    forbidden_calls = {
        "eval",
        "exec",
        "open",
        "compile",
        "__import__",
        "system",
        "popen",
        "run",
        "sleep",
        "uuid4",
        "write",
        "replace",
    }
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            assert name.casefold() not in forbidden_calls, path


def test_typed_boundary_avoids_serialization_round_trip() -> None:
    runtime = (ROOT / "runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(runtime)
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    helper = helpers["_typed_copy"]
    calls = {
        node.func.attr
        for node in ast.walk(helper)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "model_copy" in calls
    assert "model_dump" not in calls
    assert "model_dump_json" not in calls
