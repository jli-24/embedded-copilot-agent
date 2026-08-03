from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path("src/embedded_copilot/reasoning")
FORBIDDEN_IMPORT_PARTS = {
    "os",
    "pathlib",
    "socket",
    "requests",
    "httpx",
    "subprocess",
    "sqlite3",
    "git",
    "embedded_copilot.memory_automation",
    "embedded_copilot.knowledge_writer",
    "embedded_copilot.supervisor",
    "embedded_copilot.model_runtime",
    "embedded_copilot.knowledge",
    "embedded_copilot.rag",
}
FORBIDDEN_CALLS = {
    "open",
    "system",
    "popen",
    "run",
    "check_call",
    "check_output",
}


def _module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name
    return node.module or ""


def test_reasoning_layer_has_no_external_side_effect_dependencies() -> None:
    assert ROOT.exists()
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = _module_name(node)
                assert not any(
                    module == forbidden or module.startswith(forbidden + ".")
                    for forbidden in FORBIDDEN_IMPORT_PARTS
                ), f"forbidden import {module} in {path}"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS


def test_reasoning_package_does_not_contain_write_or_execution_capabilities() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in ROOT.rglob("*.py")
    ).casefold()
    for forbidden in (
        "memorycandidate",
        "knowledgeartifact",
        "engineeringevent",
        "subprocess",
        "socket",
        "filesystem",
        "write_workspace",
        "apply_patch",
    ):
        assert forbidden not in source
