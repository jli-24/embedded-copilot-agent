"""Static security boundary for the Execution Integration Runtime."""

from __future__ import annotations

import ast
from pathlib import Path

import embedded_copilot.execution_runtime as public_package

ROOT = Path(__file__).parents[2]
RUNTIME = ROOT / "src" / "embedded_copilot" / "execution_runtime"


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(RUNTIME.rglob("*.py")))


def test_execution_runtime_has_fixed_framework_independent_boundary() -> None:
    assert RUNTIME.is_dir()
    forbidden_imports = (
        "fastapi",
        "starlette",
        "streamlit",
        "langgraph",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "serial",
        "pylink",
        "pyocd",
        "docker",
        "sqlalchemy",
        "chromadb",
        "embedded_copilot.supervisor",
        "embedded_copilot.workflow_runtime",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_memory",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
    )
    agent_importers = []
    review_importers = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                assert not any(
                    name == banned or name.startswith(f"{banned}.")
                    for name in names
                    for banned in forbidden_imports
                ), path
                if any(
                    name.startswith("embedded_copilot.agent_execution")
                    for name in names
                ):
                    agent_importers.append(path.relative_to(RUNTIME).as_posix())
                if any(
                    name.startswith("embedded_copilot.human_loop") for name in names
                ):
                    review_importers.append(path.relative_to(RUNTIME).as_posix())
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                assert name not in {
                    "open",
                    "exec",
                    "eval",
                    "system",
                    "Popen",
                    "run",
                    "check_call",
                    "check_output",
                    "model_dump_json",
                }, (path, name)
    assert sorted(set(agent_importers)) == ["integration/agent_execution.py"]
    assert sorted(set(review_importers)) == ["approval/context.py"]


def test_public_exports_exclude_internal_runtime_objects() -> None:
    exported = set(public_package.__all__)
    forbidden = {
        "ExecutionExecutorBinding",
        "ExecutionExecutorRegistry",
        "ExecutionService",
        "PreparedExecution",
        "FakeExecutor",
        "RealExecutor",
    }
    assert not exported.intersection(forbidden)
    for name in ("registry", "executor", "service", "binding", "fake"):
        assert name not in {item.lower() for item in exported}


def test_runtime_contains_no_real_execution_or_persistence_primitives() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files()
    ).lower()
    for forbidden in (
        "os.system",
        "subprocess",
        "git push",
        "serial.write",
        "usb",
        "flash tool",
        "docker",
        "compiler",
        "pathlib",
        "sqlite",
        "database",
        "import_module",
        "uuid",
        "datetime.now",
        "time.time",
        "backgroundtask",
    ):
        assert forbidden not in combined
    assert "class fake" not in combined
    assert "class real" not in combined
