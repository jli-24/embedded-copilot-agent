from __future__ import annotations

import ast
from pathlib import Path

from embedded_copilot.agents.debug import DebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.services.canonical_runtime import (
    CANONICAL_RUNTIME_AGENT_NAMES,
    CANONICAL_RUNTIME_AGENT_TYPES,
    CANONICAL_RUNTIME_ROUTER,
)


SOURCE_ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
KNOWLEDGE_PACKAGES = (
    "rag",
    "knowledge",
    "engineering_knowledge",
    "knowledge_evolution",
    "knowledge_writer",
    "datasheet_agent",
    "web_research_agent",
)


def test_knowledge_agent_is_the_only_runtime_knowledge_entry() -> None:
    assert CANONICAL_RUNTIME_AGENT_NAMES == (
        "supervisor",
        "knowledge",
        "firmware",
        "debug",
    )
    assert KnowledgeAgent in CANONICAL_RUNTIME_AGENT_TYPES
    assert CANONICAL_RUNTIME_ROUTER.__name__ == "supervisor_node"
    assert set(CANONICAL_RUNTIME_AGENT_TYPES) == {
        KnowledgeAgent,
        FirmwareAgent,
        DebugAgent,
    }


def test_knowledge_packages_do_not_register_agents() -> None:
    forbidden_modules = {
        "embedded_copilot.agents.registry",
        "embedded_copilot.services.canonical_runtime",
        "embedded_copilot.services.legacy_runtime",
    }
    for package_name in KNOWLEDGE_PACKAGES:
        for path in (SOURCE_ROOT / package_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is not None:
                    assert node.module not in forbidden_modules, (path, node.module)
                    assert all(
                        alias.name != "AgentRegistry" for alias in node.names
                    ), path
                if isinstance(node, ast.Call):
                    function_name = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else node.func.id
                        if isinstance(node.func, ast.Name)
                        else None
                    )
                    assert function_name not in {"register_agent"}, path


def test_external_and_projection_modules_are_not_canonical_agent_types() -> None:
    forbidden_prefixes = (
        "embedded_copilot.rag",
        "embedded_copilot.knowledge",
        "embedded_copilot.engineering_knowledge",
        "embedded_copilot.knowledge_evolution",
        "embedded_copilot.knowledge_writer",
        "embedded_copilot.datasheet_agent",
        "embedded_copilot.web_research_agent",
    )
    assert all(
        not any(
            agent_type.__module__ == prefix
            or agent_type.__module__.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
        for agent_type in CANONICAL_RUNTIME_AGENT_TYPES
    )
