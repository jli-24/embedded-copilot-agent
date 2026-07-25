from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE_ROOT = ROOT / "src" / "embedded_copilot"
TARGETS = (
    PACKAGE_ROOT / "intelligence",
    PACKAGE_ROOT / "search",
    PACKAGE_ROOT / "conversation",
    PACKAGE_ROOT / "knowledge" / "manager.py",
    PACKAGE_ROOT / "knowledge" / "retriever.py",
    PACKAGE_ROOT / "knowledge" / "source.py",
    PACKAGE_ROOT / "knowledge" / "trace.py",
    PACKAGE_ROOT / "intelligence" / "esp32.py",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.hardware_design.artifact",
    "embedded_copilot.hardware_design.evidence",
    "embedded_copilot.hardware_design.decision",
    "embedded_copilot.hardware_design.approval",
    "sqlite3",
    "sqlalchemy",
    "shelve",
)
FORBIDDEN_LIFECYCLE_NAMES = {
    "HardwareDesignArtifact",
    "HardwareDesignEvidence",
    "DesignDecision",
    "DesignApproval",
}
FORBIDDEN_FIELDS = {
    "gpio",
    "component",
    "components",
    "connection",
    "connections",
    "voltage",
    "current",
    "electrical_parameter",
    "artifact_decision",
}


def _python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_dir():
            files.extend(target.rglob("*.py"))
        elif target.is_file():
            files.append(target)
    return tuple(sorted(set(files)))


def _name(value: ast.expr) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def test_intelligence_layer_has_no_engineering_lifecycle_imports() -> None:
    assert _python_files()
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES)
                    for alias in node.names
                ), path
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), path
                assert not (
                    {alias.name for alias in node.names} & FORBIDDEN_LIFECYCLE_NAMES
                ), path


def test_intelligence_layer_has_no_lifecycle_calls_or_dynamic_bypass() -> None:
    forbidden_calls = {
        ("artifact", "create"),
        ("artifact", "update"),
        ("artifact", "delete"),
        ("decision", "create"),
        ("decision", "update"),
        ("approval", "transition"),
    }
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            assert _name(node.func) not in {
                "getattr",
                "__import__",
                "import_module",
            }, path
            if isinstance(node.func, ast.Attribute):
                owner = _name(node.func.value)
                assert (owner, node.func.attr) not in forbidden_calls, path


def test_intelligence_layer_defines_no_engineering_fact_fields() -> None:
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
