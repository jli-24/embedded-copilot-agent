from __future__ import annotations

import ast
from pathlib import Path


def test_api_layer_does_not_import_domain_agent_implementations() -> None:
    api_root = Path("src/embedded_copilot/api")
    forbidden = (
        "embedded_copilot.agents",
        "embedded_copilot.supervisor",
        "embedded_copilot.firmware",
        "embedded_copilot.hardware",
        "embedded_copilot.pcb",
        "embedded_copilot.debug",
        "embedded_copilot.knowledge",
    )
    violations: list[str] = []
    for path in api_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        if any(module.startswith(forbidden) for module in imports):
            violations.append(path.name)

    assert violations == []
