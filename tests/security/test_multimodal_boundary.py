from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE_ROOT = ROOT / "src" / "embedded_copilot"
WEB_ROOT = ROOT / "web" / "copilot"
TARGETS = (
    PACKAGE_ROOT / "intelligence",
    PACKAGE_ROOT / "multimodal" / "context.py",
    PACKAGE_ROOT / "vision",
    PACKAGE_ROOT / "file_runtime",
    PACKAGE_ROOT / "datasheet" / "intelligence",
    PACKAGE_ROOT / "conversation",
    PACKAGE_ROOT / "api" / "copilot_models.py",
    PACKAGE_ROOT / "api" / "copilot_routes.py",
    PACKAGE_ROOT / "services" / "experience_runtime.py",
    WEB_ROOT,
)
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.hardware_design.artifact",
    "embedded_copilot.hardware_design.evidence",
    "embedded_copilot.hardware_design.decision",
    "embedded_copilot.hardware_design.approval",
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "langgraph",
    "openai",
    "chromadb",
    "sqlite3",
    "sqlalchemy",
    "shelve",
)
FORBIDDEN_FIELDS = {
    "gpio",
    "component",
    "components",
    "connection",
    "connections",
    "voltage",
    "current",
    "artifact_update",
}


def _python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_dir():
            files.extend(target.rglob("*.py"))
        elif target.is_file():
            files.append(target)
    result = tuple(sorted(set(files)))
    assert result
    return result


def _name(value: ast.expr) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def test_v025_has_no_forbidden_runtime_dependencies() -> None:
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES)
                    for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    FORBIDDEN_IMPORT_PREFIXES
                ), path


def test_v025_has_no_lifecycle_mutation_or_dynamic_bypass() -> None:
    forbidden_calls = {
        ("artifact", "create"),
        ("artifact", "update"),
        ("artifact", "delete"),
        ("decision", "create"),
        ("decision", "update"),
        ("evidence", "create"),
        ("evidence", "update"),
        ("approval", "transition"),
    }
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            assert _name(node.func) not in {
                "__import__",
                "import_module",
            }, path
            if isinstance(node.func, ast.Attribute):
                assert (
                    _name(node.func.value),
                    node.func.attr,
                ) not in forbidden_calls, path


def test_v025_defines_no_engineering_fact_fields() -> None:
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                assert _name(node.target) not in FORBIDDEN_FIELDS, path
            elif isinstance(node, ast.Assign):
                assert all(
                    _name(target) not in FORBIDDEN_FIELDS for target in node.targets
                ), path
            elif isinstance(node, ast.keyword) and node.arg is not None:
                assert node.arg not in FORBIDDEN_FIELDS, path


def test_v025_has_no_persistence_or_browser_file_payload_controls() -> None:
    forbidden_calls = {"write_text", "write_bytes", "file_uploader"}
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            assert _name(node.func) not in forbidden_calls, path
