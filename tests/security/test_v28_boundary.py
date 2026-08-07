from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
PACKAGE = ROOT / "src" / "embedded_copilot" / "engineering_completion"
ROUTE = (
    ROOT / "src" / "embedded_copilot" / "api" / "engineering_completion_v28_routes.py"
)


def _modules() -> list[Path]:
    return [*PACKAGE.rglob("*.py"), ROUTE]


def test_v28_import_boundary_is_projection_only() -> None:
    forbidden_modules = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "sqlite3",
        "pathlib",
        "os",
        "git",
    }
    forbidden_names = {
        "BuildAgent",
        "FlashAgent",
        "DeviceAgent",
        "EngineeringAgent",
        "LLM",
        "ModelRuntime",
        "ReasoningRuntime",
        "MemoryWriter",
        "KnowledgeWriter",
    }
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name.split(".")[0] not in forbidden_modules
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden_modules
            if isinstance(node, ast.Name):
                assert node.id not in forbidden_names
