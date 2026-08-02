from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "engineering_intelligence"


def _trees() -> dict[Path, ast.Module]:
    return {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in PACKAGE.rglob("*.py")
    }


def test_engineering_intelligence_has_no_framework_io_or_execution_dependencies() -> (
    None
):
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
        "threading",
        "asyncio",
        "sqlite3",
        "sqlalchemy",
        "supervisor",
        "agent_execution",
        "execution_runtime",
        "tool_runtime",
        "workspace_runtime",
    )
    for path, tree in _trees().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                continue
            assert not any(
                token in module for token in forbidden for module in modules
            ), (
                path,
                modules,
            )


def test_existing_contract_imports_are_confined_to_projection_adapters() -> None:
    allowed = {
        "embedded_copilot.engineering_interface": "integration/project.py",
        "embedded_copilot.knowledge.intelligence": "integration/knowledge.py",
        "embedded_copilot.engineering_memory.context": "integration/memory.py",
        "embedded_copilot.datasheet_runtime": "integration/datasheet.py",
    }
    for path, tree in _trees().items():
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            for module, expected in allowed.items():
                if node.module.startswith(module):
                    assert relative == expected
                    assert node.module == module


def test_package_has_no_io_dynamic_import_or_mutable_state() -> None:
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


def test_contracts_do_not_expose_payload_or_control_fields() -> None:
    from embedded_copilot import engineering_intelligence as public

    forbidden = {
        "path",
        "content",
        "bytes",
        "base64",
        "command",
        "tool_call",
        "agent_route",
        "provider",
        "credential",
        "control_action",
    }
    for name in public.__all__:
        value = getattr(public, name)
        fields = getattr(value, "model_fields", {})
        assert forbidden.isdisjoint(fields), (name, forbidden & set(fields))
