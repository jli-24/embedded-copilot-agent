from __future__ import annotations

import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
SERVICE_NAME_SUFFIXES = (
    "_service",
    "_projection",
    "_writer",
    "_memory",
    "_context",
    "_knowledge",
)

# These files are compatibility implementations, not Engineering Services.
# They are checked by the Legacy Runtime boundary tests instead.
LEGACY_ADAPTER_FILES = {Path("hardware_design/adapter.py")}
LEGACY_COMPATIBILITY_FILES = {
    Path("hardware/agent.py"),
    Path("pcb/agent.py"),
    Path("supervisor/agent.py"),
    Path("firmware/agent.py"),
    Path("debug/agent.py"),
}

FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "embedded_copilot.firmware.agent",
    "embedded_copilot.debug.agent",
    "embedded_copilot.hardware.agent",
    "embedded_copilot.pcb.agent",
    "embedded_copilot.services.canonical_runtime",
    "embedded_copilot.services.legacy_runtime",
    "langgraph",
)


def _files_under_service_packages() -> tuple[Path, ...]:
    excluded = {item.as_posix() for item in LEGACY_ADAPTER_FILES}
    return tuple(
        path
        for package in sorted(SOURCE_ROOT.iterdir())
        if package.is_dir()
        and (
            package.name.startswith("engineering_")
            or package.name.endswith(SERVICE_NAME_SUFFIXES)
            or package.name == "multimodal_input"
        )
        for path in sorted(package.rglob("*.py"))
        if path.relative_to(SOURCE_ROOT).as_posix() not in excluded
    )


def _imports(tree: ast.AST) -> tuple[tuple[str, tuple[str, ...]], ...]:
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.module, tuple(alias.name for alias in node.names)))
    return tuple(imports)


def test_engineering_services_have_no_runtime_agent_imports() -> None:
    for path in _files_under_service_packages():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module, names in _imports(tree):
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ), (path, module)
            assert "BaseAgent" not in names
            assert "SupervisorAgent" not in names


def test_engineering_services_do_not_inherit_or_invoke_agent_loops() -> None:
    for path in _files_under_service_packages():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {
                    base.id for base in node.bases if isinstance(base, ast.Name)
                }
                assert not base_names.intersection(
                    {"BaseAgent", "SupervisorAgent"}
                ), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"run", "invoke"}, path


def test_legacy_compatibility_exceptions_are_explicit() -> None:
    for relative in LEGACY_COMPATIBILITY_FILES | LEGACY_ADAPTER_FILES:
        path = SOURCE_ROOT / relative
        assert path.is_file(), relative
