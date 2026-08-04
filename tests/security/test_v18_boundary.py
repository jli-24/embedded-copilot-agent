from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
TARGETS = (
    ROOT / "model_runtime" / "contracts.py",
    ROOT / "model_runtime" / "models.py",
    ROOT / "model_runtime" / "service.py",
    ROOT / "model_runtime" / "factory.py",
    ROOT / "model_runtime" / "exceptions.py",
    ROOT / "model_runtime" / "adapters",
    ROOT / "workspace_projection",
    ROOT / "toolchain",
    ROOT / "component_recommendation",
)

FORBIDDEN_MODULES = {
    "os",
    "pathlib",
    "subprocess",
    "socket",
    "httpx",
    "requests",
    "sqlite3",
}


def _files() -> tuple[Path, ...]:
    values: list[Path] = []
    for target in TARGETS:
        values.extend((target,) if target.is_file() else target.rglob("*.py"))
    return tuple(values)


def test_v18_core_does_not_import_external_mutation_or_provider_runtime() -> None:
    for path in _files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                assert not names & FORBIDDEN_MODULES, path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_MODULES, path
                imported = node.module or ""
                assert "supervisor" not in imported
                assert "knowledge_writer" not in imported
                assert "memory_automation" not in imported
                assert "reasoning_runtime" not in imported
