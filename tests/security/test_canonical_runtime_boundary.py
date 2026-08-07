from __future__ import annotations

import ast
from pathlib import Path


CANONICAL_RUNTIME_MODULE = (
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "services"
    / "canonical_runtime.py"
)

FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.hardware",
    "embedded_copilot.pcb",
    "embedded_copilot.services.legacy_runtime",
    "embedded_copilot.supervisor.agent",
    "embedded_copilot.firmware.agent",
    "embedded_copilot.debug.agent",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_canonical_runtime_has_no_legacy_import_path() -> None:
    imported = _imported_modules(CANONICAL_RUNTIME_MODULE)

    for forbidden in FORBIDDEN_IMPORT_PREFIXES:
        assert all(
            module != forbidden and not module.startswith(f"{forbidden}.")
            for module in imported
        ), (forbidden, imported)


def test_canonical_runtime_uses_only_canonical_agent_modules() -> None:
    imported = _imported_modules(CANONICAL_RUNTIME_MODULE)

    assert "embedded_copilot.agents.knowledge" in imported
    assert "embedded_copilot.agents.firmware" in imported
    assert "embedded_copilot.agents.debug" in imported
    assert "embedded_copilot.agents.supervisor" in imported
