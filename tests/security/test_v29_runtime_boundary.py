from __future__ import annotations

import ast
from pathlib import Path

from embedded_copilot.services.canonical_runtime import (
    CANONICAL_RUNTIME_AGENT_NAMES,
    CANONICAL_RUNTIME_AGENT_TYPES,
    CANONICAL_RUNTIME_ROUTER,
)


ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "multimodal_input"
ROUTE = ROOT / "src" / "embedded_copilot" / "api" / "multimodal_v29_routes.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.autonomous_loop",
    "embedded_copilot.build",
    "embedded_copilot.device",
    "embedded_copilot.flash",
    "embedded_copilot.hardware",
    "embedded_copilot.legacy_runtime",
    "embedded_copilot.services",
    "embedded_copilot.tool_adapter",
    "embedded_copilot.tools",
    "embedded_copilot.workflow",
    "embedded_copilot.*_runtime",
    "langgraph",
)
FORBIDDEN_MODULES = {
    "asyncio",
    "httpx",
    "openai",
    "anthropic",
    "os",
    "pathlib",
    "requests",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
    "websockets",
}
FORBIDDEN_NAMES = {
    "Agent",
    "BaseAgent",
    "BuildAgent",
    "DatasheetAgent",
    "DeviceControl",
    "DocumentVisionAgent",
    "FlashAgent",
    "HardwareAgent",
    "ImageAgent",
    "PCBVisionAgent",
    "VisionAgent",
    "Workflow",
    "build_legacy_runtime",
    "build_runtime",
}
FORBIDDEN_ATTRIBUTES = {
    "dispatch",
    "execute",
    "invoke",
    "run",
}


def _module_name(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    del tree
    return path.as_posix()


def _assert_boundary(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in FORBIDDEN_MODULES, _module_name(path)
                assert not any(
                    alias.name == prefix or alias.name.startswith(f"{prefix}.")
                    for prefix in FORBIDDEN_IMPORT_PREFIXES
                ), (path, alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module.split(".", 1)[0] not in FORBIDDEN_MODULES, _module_name(path)
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ), (path, module)
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, (path, node.id)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRIBUTES, (path, node.attr)


def test_multimodal_package_and_route_are_runtime_isolated() -> None:
    for path in (*PACKAGE.rglob("*.py"), ROUTE):
        _assert_boundary(path)


def test_multimodal_is_not_registered_as_a_canonical_runtime_agent() -> None:
    assert CANONICAL_RUNTIME_AGENT_NAMES == (
        "supervisor",
        "knowledge",
        "firmware",
        "debug",
    )
    assert tuple(agent.__module__ for agent in CANONICAL_RUNTIME_AGENT_TYPES) == (
        "embedded_copilot.agents.knowledge",
        "embedded_copilot.agents.firmware",
        "embedded_copilot.agents.debug",
    )
    assert CANONICAL_RUNTIME_ROUTER.__name__ == "supervisor_node"
    assert all(
        agent.__module__ != "embedded_copilot.multimodal_input"
        for agent in CANONICAL_RUNTIME_AGENT_TYPES
    )
