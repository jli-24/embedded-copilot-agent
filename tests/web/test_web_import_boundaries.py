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
        "embedded_copilot.evaluation.runner",
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


def test_streamlit_app_uses_product_api_as_its_only_analysis_boundary() -> None:
    source = Path("web/app.py").read_text(encoding="utf-8")

    assert "ProductApiClient" in source
    assert "EvaluationRunner" not in source
    assert ".run(" not in source
