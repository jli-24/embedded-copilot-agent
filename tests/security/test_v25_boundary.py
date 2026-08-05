from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
TARGETS = [ROOT / "hil_validation", ROOT / "api" / "hil_v25_routes.py"]
FORBIDDEN = {
    "os",
    "pathlib",
    "shutil",
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "sqlite3",
    "model_runtime",
    "reasoning_runtime",
    "knowledge_writer",
    "workspace_runtime",
    "workspace_projection",
    "HardwareAgent",
    "HILAgent",
    "DeviceAgent",
    "TestAgent",
    "ValidationAgent",
}


def test_v25_layer_has_no_external_or_agent_dependencies() -> None:
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

