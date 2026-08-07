from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
TARGETS = [ROOT / "knowledge_evolution", ROOT / "api" / "knowledge_v27_routes.py"]
FORBIDDEN = {
    "os", "pathlib", "shutil", "subprocess", "socket", "requests", "httpx", "sqlite3",
    "tool_adapter", "toolchain", "workspace_runtime", "workspace_projection", "autonomous_loop",
    "model_runtime", "reasoning_runtime", "knowledge_writer", "MemoryAgent", "KnowledgeAgent",
    "RecommendationAgent",
}


def test_v27_layer_has_no_external_or_agent_dependencies() -> None:
    paths = [path for root in TARGETS for path in (root.rglob("*.py") if root.is_dir() else (root,))]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {item.name.split(".")[0] for item in node.names} & FORBIDDEN, path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN, path
            if isinstance(node, ast.Name):
                assert node.id not in FORBIDDEN, path
