from __future__ import annotations

import ast
from pathlib import Path

import embedded_copilot.optimization as public_package

ROOT = Path(__file__).parents[2]
RUNTIME = ROOT / "src" / "embedded_copilot" / "optimization"


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(RUNTIME.rglob("*.py")))


def test_optimization_runtime_has_no_execution_or_device_dependencies() -> None:
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
        "usb",
        "docker",
        "pathlib",
        "sqlalchemy",
        "chromadb",
        "threading",
        "embedded_copilot.supervisor",
        "embedded_copilot.workflow_runtime",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_memory",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.agent_execution",
        "embedded_copilot.execution_runtime",
    )
    hardware_importers = []
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
                    name.startswith("embedded_copilot.hardware_intelligence")
                    for name in names
                ):
                    hardware_importers.append(path.relative_to(RUNTIME).as_posix())
            if isinstance(node, ast.Call):
                called = ""
                if isinstance(node.func, ast.Name):
                    called = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    called = node.func.attr
                assert called not in {
                    "open",
                    "exec",
                    "eval",
                    "system",
                    "Popen",
                    "connect",
                    "send",
                    "write",
                    "flash",
                    "debug",
                    "control",
                    "model_dump_json",
                }, (path, called)
    assert sorted(set(hardware_importers)) == ["integration/hardware_intelligence.py"]


def test_optimization_source_has_no_side_effect_or_persistence_primitives() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files()
    ).lower()
    for forbidden in (
        "os.system",
        "import_module",
        "datetime.now",
        "time.time",
        "uuid",
        "backgroundtask",
        "filesystem write",
        "database connection",
        "hardware control",
        "real pid controller",
        "online parameter tuning",
    ):
        assert forbidden not in combined


def test_public_exports_hide_concrete_algorithms_evaluator_and_ledger() -> None:
    exported = set(public_package.__all__)
    assert not exported.intersection(
        {
            "PIDOptimizer",
            "PowerOptimizer",
            "PerformanceOptimizer",
            "DeterministicEvaluator",
            "OptimizationLedger",
        }
    )
