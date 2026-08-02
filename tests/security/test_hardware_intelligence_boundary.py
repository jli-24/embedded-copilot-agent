"""Static security boundary for the Hardware Intelligence Runtime."""

from __future__ import annotations

import ast
from pathlib import Path

import embedded_copilot.hardware_intelligence as public_package

ROOT = Path(__file__).parents[2]
RUNTIME = ROOT / "src" / "embedded_copilot" / "hardware_intelligence"


def _python_files() -> tuple[Path, ...]:
    return tuple(sorted(RUNTIME.rglob("*.py")))


def test_hardware_intelligence_is_framework_and_device_independent() -> None:
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
        "usb",
        "pyserial",
        "openocd",
        "jlink",
        "esptool",
        "pylink",
        "pyocd",
        "sqlalchemy",
        "chromadb",
        "pathlib",
        "embedded_copilot.supervisor",
        "embedded_copilot.workflow_runtime",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_memory",
        "embedded_copilot.tool_runtime",
    )
    execution_importers = []
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
                    name.startswith("embedded_copilot.execution_runtime")
                    for name in names
                ):
                    execution_importers.append(path.relative_to(RUNTIME).as_posix())
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
                    "reset",
                    "flash",
                    "program",
                    "model_dump_json",
                }, (path, called)
    assert sorted(set(execution_importers)) == ["integration/execution.py"]


def test_runtime_contains_no_control_or_persistence_primitives() -> None:
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
        "device sdk",
        "gpio control",
        "power control",
        "memory store",
        "database connection",
    ):
        assert forbidden not in combined
    assert "class fake" not in combined
    assert "class real" not in combined


def test_public_exports_do_not_expose_internal_services_or_devices() -> None:
    exported = set(public_package.__all__)
    forbidden = {
        "DigitalTwinService",
        "HardwareValidationService",
        "HardwareRuntimeService",
        "DeviceConnection",
        "HardwareController",
        "FakeTwinProvider",
    }
    assert not exported.intersection(forbidden)
