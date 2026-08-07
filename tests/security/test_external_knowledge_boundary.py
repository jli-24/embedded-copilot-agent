from __future__ import annotations

import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
EXTERNAL_PACKAGES = ("datasheet_agent", "web_research_agent")
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "embedded_copilot.firmware.agent",
    "embedded_copilot.debug.agent",
    "embedded_copilot.services.canonical_runtime",
    "embedded_copilot.services.legacy_runtime",
    "embedded_copilot.agents.workflow",
    "langgraph",
)


def _files() -> tuple[Path, ...]:
    return tuple(
        path
        for package_name in EXTERNAL_PACKAGES
        for path in sorted((SOURCE_ROOT / package_name).rglob("*.py"))
    )


def _imports(tree: ast.AST) -> tuple[tuple[str, tuple[str, ...]], ...]:
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.module, tuple(alias.name for alias in node.names)))
    return tuple(imports)


def test_external_knowledge_modules_are_adapter_or_projection_only() -> None:
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module, names in _imports(tree):
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ), (path, module)
            assert "BaseAgent" not in names
            assert "SupervisorAgent" not in names
            assert "AgentRegistry" not in names
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith("Agent"), path
                base_names = {
                    base.id for base in node.bases if isinstance(base, ast.Name)
                }
                assert "BaseAgent" not in base_names, path


def test_external_knowledge_modules_do_not_create_execution_or_workflow() -> None:
    forbidden_calls = {
        "build_workflow",
        "supervisor_node",
        "register_agent",
        "run",
        "invoke",
        "execute",
        "flash",
    }
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else None
                )
                assert function_name not in forbidden_calls, (path, function_name)


def test_external_knowledge_packages_exist() -> None:
    for package_name in EXTERNAL_PACKAGES:
        assert (SOURCE_ROOT / package_name).is_dir(), package_name
