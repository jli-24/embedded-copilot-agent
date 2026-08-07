from __future__ import annotations

import ast
from pathlib import Path

from embedded_copilot.agents.debug import DebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.multimodal_input import MultimodalInputService
from embedded_copilot.services.canonical_runtime import CANONICAL_RUNTIME_AGENT_TYPES


PACKAGE = Path(__file__).parents[2] / "src" / "embedded_copilot" / "multimodal_input"
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.supervisor",
    "embedded_copilot.tool_runtime",
    "embedded_copilot.tool_adapter",
    "langgraph",
    "openai",
    "anthropic",
    "requests",
    "urllib",
    "socket",
    "subprocess",
    "sqlite3",
)


def _module_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    return tuple(modules)


def test_multimodal_service_has_only_port_and_projection_dependencies() -> None:
    for path in PACKAGE.rglob("*.py"):
        for module in _module_imports(path):
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ), (path, module)
            assert not module.endswith("_runtime"), (path, module)


def test_multimodal_package_does_not_define_agent_types() -> None:
    forbidden_names = {"VisionAgent", "DatasheetAgent", "PCBVisionAgent"}
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in forbidden_names, path
            if isinstance(node, ast.ImportFrom):
                assert not any(alias.name in forbidden_names for alias in node.names)


def test_multimodal_service_is_not_a_canonical_runtime_agent() -> None:
    assert MultimodalInputService not in CANONICAL_RUNTIME_AGENT_TYPES
    assert {KnowledgeAgent, FirmwareAgent, DebugAgent} == set(
        CANONICAL_RUNTIME_AGENT_TYPES
    )
