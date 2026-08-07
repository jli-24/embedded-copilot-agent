from __future__ import annotations

import ast
from pathlib import Path

from embedded_copilot.knowledge_evolution.adapters.memory import (
    EngineeringMemoryProjectionAdapter,
)


def test_knowledge_evolution_package_has_no_reverse_memory_automation_dependency() -> None:
    root = Path("src/embedded_copilot/knowledge_evolution")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any("memory_automation" in item for item in imports)
    assert not any("MemoryCandidate" in item for item in imports)
    assert "to_memory_input" not in source


def test_engineering_memory_adapter_is_read_only_projection() -> None:
    assert hasattr(EngineeringMemoryProjectionAdapter, "get_snapshot")
    assert not hasattr(EngineeringMemoryProjectionAdapter, "write")
