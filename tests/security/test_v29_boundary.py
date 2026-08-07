from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "multimodal_input"
ROUTE = ROOT / "src" / "embedded_copilot" / "api" / "multimodal_v29_routes.py"


def test_v29_boundary_has_no_external_runtime_imports_or_agents() -> None:
    forbidden_modules = {
        "aiohttp",
        "anthropic",
        "asyncio",
        "chromadb",
        "os",
        "pathlib",
        "openai",
        "requests",
        "subprocess",
        "socket",
        "torch",
        "transformers",
        "httpx",
        "sqlite3",
        "urllib",
        "websockets",
    }
    forbidden_prefixes = (
        "embedded_copilot.agents",
        "embedded_copilot.autonomous_loop",
        "embedded_copilot.build",
        "embedded_copilot.device",
        "embedded_copilot.flash",
        "embedded_copilot.firmware",
        "embedded_copilot.hardware",
        "embedded_copilot.services",
        "embedded_copilot.tool_adapter",
        "embedded_copilot.tools",
        "embedded_copilot.*_runtime",
        "embedded_copilot.workflow",
    )
    forbidden_names = {
        "Agent",
        "BuildAgent",
        "DeviceControl",
        "FlashAgent",
        "HardwareAgent",
        "VisionAgent",
        "DatasheetAgent",
        "PcbAgent",
        "ModelRuntime",
        "ReasoningRuntime",
        "ToolRuntime",
        "Workflow",
        "build_legacy_runtime",
        "build_runtime",
        "create_reasoning_runtime",
        "create_vision_runtime",
    }
    forbidden_attributes = {
        "connect",
        "execute",
        "open",
        "read_bytes",
        "read_text",
        "run",
        "write_bytes",
        "write_text",
    }
    for path in [*PACKAGE.rglob("*.py"), ROUTE]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if path == ROUTE:
            assert not any(
                isinstance(node, ast.Import)
                and any(alias.name == "importlib" for alias in node.names)
                for node in ast.walk(tree)
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] not in forbidden_modules
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module.split(".")[0] not in forbidden_modules
                assert not any(module.startswith(prefix) for prefix in forbidden_prefixes)
                parts = module.split(".")
                assert not (
                    len(parts) > 1
                    and parts[0] == "embedded_copilot"
                    and parts[1].endswith("_runtime")
                )
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_names
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden_attributes
