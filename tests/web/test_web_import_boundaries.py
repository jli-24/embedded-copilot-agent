from __future__ import annotations

import ast
from pathlib import Path


def test_streamlit_layer_does_not_import_runtime_implementation_modules() -> None:
    forbidden = (
        "embedded_copilot.agents",
        "embedded_copilot.supervisor",
        "embedded_copilot.pcb",
        "embedded_copilot.datasheet",
        "embedded_copilot.knowledge",
        "embedded_copilot.multimodal",
    )
    violations: list[str] = []
    for path in Path("web").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        if any(module.startswith(forbidden) for module in imports):
            violations.append(path.name)

    assert violations == []
