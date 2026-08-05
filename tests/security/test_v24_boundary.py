from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
TARGETS = [
    ROOT / "firmware_engineering",
    ROOT / "api" / "firmware_v24_routes.py",
]
FORBIDDEN = {
    "os",
    "pathlib",
    "shutil",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "sqlite3",
    "workspace_runtime",
    "workspace_projection",
    "model_runtime",
    "reasoning_runtime",
    "knowledge_writer",
    "FirmwareAgent",
    "BuildAgent",
    "CompilerAgent",
    "FlashAgent",
    "DeviceAgent",
}


def test_v24_layer_has_no_external_or_agent_dependencies() -> None:
    paths = [
        path
        for root in TARGETS
        for path in (root.rglob("*.py") if root.is_dir() else (root,))
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {item.name.split(".")[0] for item in node.names} & FORBIDDEN, path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN, path
            if isinstance(node, ast.Name):
                assert node.id not in FORBIDDEN, path
