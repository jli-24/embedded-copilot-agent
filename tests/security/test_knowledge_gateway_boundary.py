from __future__ import annotations

import ast
from pathlib import Path


SOURCE_ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
PACKAGE_NAMES = (
    "rag",
    "knowledge",
    "engineering_knowledge",
    "knowledge_evolution",
    "knowledge_writer",
    "multimodal_input",
    "datasheet",
    "datasheet_agent",
    "web_research_agent",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "embedded_copilot.firmware.agent",
    "embedded_copilot.debug.agent",
    "embedded_copilot.services.canonical_runtime",
    "embedded_copilot.services.legacy_runtime",
    "embedded_copilot.agents.workflow",
    "langgraph",
    "embedded_copilot.memory_automation.application",
    "embedded_copilot.memory_automation.factory",
    "embedded_copilot.memory_automation.projector",
    "embedded_copilot.memory_automation.promotion",
    "embedded_copilot.memory_automation.service",
    "embedded_copilot.engineering_memory.store",
)


def _files() -> tuple[Path, ...]:
    return tuple(
        path
        for package_name in PACKAGE_NAMES
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


def test_knowledge_packages_have_no_runtime_agent_imports() -> None:
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


def test_knowledge_packages_do_not_create_runtime_or_execution_edges() -> None:
    forbidden_calls = {
        "build_workflow",
        "supervisor_node",
        "register_agent",
        "run",
        "invoke",
        "flash",
        "execute_device",
    }
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {
                    base.id for base in node.bases if isinstance(base, ast.Name)
                }
                assert not base_names.intersection(
                    {"BaseAgent", "SupervisorAgent"}
                ), path
            if isinstance(node, ast.Call):
                function_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else None
                )
                assert function_name not in forbidden_calls, (path, function_name)


def test_knowledge_gateway_packages_exist_as_explicit_boundaries() -> None:
    for package_name in PACKAGE_NAMES:
        assert (SOURCE_ROOT / package_name).is_dir(), package_name
