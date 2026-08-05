from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
FORBIDDEN = {"subprocess", "socket", "requests", "httpx", "sqlite3", "pathlib"}
FORBIDDEN_AGENTS = {
    "AutonomousAgent",
    "LoopAgent",
    "PlanningAgent",
    "RepairAgent",
    "ValidationAgent",
    "DeviceAgent",
}


def test_v20_packages_do_not_depend_on_execution_resources_or_agents() -> None:
    paths = [ROOT / "autonomous_loop", ROOT / "approval_gate"]
    for path in paths:
        for file in path.rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            text = file.read_text(encoding="utf-8")
            assert not any(name in text for name in FORBIDDEN_AGENTS)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(
                        alias.name.split(".")[0] not in FORBIDDEN
                        for alias in node.names
                    )
                if isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[0] not in FORBIDDEN
