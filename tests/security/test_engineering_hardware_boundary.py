from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "engineering_hardware"


def _trees() -> dict[Path, ast.Module]:
    return {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in PACKAGE.rglob("*.py")
    }


def test_hardware_engineering_has_no_framework_io_or_execution_dependency() -> None:
    forbidden = (
        "fastapi",
        "starlette",
        "streamlit",
        "gradio",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "pathlib",
        "os",
        "random",
        "uuid",
        "threading",
        "asyncio",
        "sqlite3",
        "sqlalchemy",
        "supervisor",
        "agent_execution",
        "execution_runtime",
        "tool_runtime",
        "workspace_runtime",
        "engineering_generation",
        "hardware_intelligence",
        "hardware_design",
        "embedded_copilot.hardware",
        "human_loop",
        "engineering_memory",
        "embedded_copilot.knowledge",
    )
    for path, tree in _trees().items():
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        assert not any(token in module for token in forbidden for module in modules), (
            path,
            modules,
        )


def test_engineering_intelligence_import_is_confined_to_typed_adapter() -> None:
    for path, tree in _trees().items():
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module.startswith("embedded_copilot.engineering_intelligence"):
                assert relative == "integration/intelligence.py"
                assert node.module == "embedded_copilot.engineering_intelligence"


def test_package_has_no_io_control_dynamic_import_or_serialization_rebuild() -> None:
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "__import__",
        "model_dump_json",
        "read",
        "write",
        "send",
        "connect",
        "run",
        "start",
        "sleep",
        "flash",
        "program",
        "reset",
        "control",
    }
    for path, tree in _trees().items():
        for node in ast.walk(tree):
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                raise AssertionError(f"mutable state in {path}")
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            assert name not in forbidden_calls, (path, name)


def test_typed_inputs_are_not_rebuilt_through_serialization() -> None:
    for path, tree in _trees().items():
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr == "model_dump":
                assert relative == "models.py"


def test_public_contracts_do_not_expose_control_or_eda_fields() -> None:
    from embedded_copilot import engineering_hardware as public

    forbidden = {
        "path",
        "content",
        "bytes",
        "base64",
        "command",
        "tool_call",
        "provider",
        "credential",
        "pin_mapping",
        "netlist",
        "footprint",
        "coordinate",
        "write_action",
    }
    for name in public.__all__:
        value = getattr(public, name)
        fields = getattr(value, "model_fields", {})
        assert forbidden.isdisjoint(fields), (name, forbidden & set(fields))


def test_root_package_exports_only_stable_public_boundary() -> None:
    from embedded_copilot import engineering_hardware as public

    for forbidden in (
        "HardwareEngineeringAgent",
        "ComponentSelector",
        "ArchitectureProjector",
        "PCBProjector",
        "ReviewProjector",
    ):
        assert not hasattr(public, forbidden)
