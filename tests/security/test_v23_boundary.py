from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
TARGETS = [ROOT / "debug_analysis", ROOT / "optimization", ROOT / "api" / "debug_v23_routes.py", ROOT / "api" / "optimization_v23_routes.py"]
FORBIDDEN = {"os", "pathlib", "shutil", "subprocess", "socket", "requests", "httpx", "sqlite3", "tool_adapter", "workspace_runtime", "workspace_projection", "autonomous_loop", "knowledge_writer", "model_runtime", "Supervisor", "DebugAgent", "OptimizationAgent", "RepairAgent"}


def test_v23_layers_are_projection_only() -> None:
    paths = [p for root in TARGETS for p in (root.rglob("*.py") if root.is_dir() else (root,))]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {item.name.split(".")[0] for item in node.names} & FORBIDDEN, path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN, path
            if isinstance(node, ast.Name):
                assert node.id not in FORBIDDEN, path
