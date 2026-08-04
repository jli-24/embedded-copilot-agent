from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_generation")
FORBIDDEN = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "pathlib",
    "sqlite3",
    "git",
    "openai",
    "ollama",
    "transformers",
    "supervisor",
    "model_runtime",
    "reasoning",
    "llm",
    "knowledge_writer",
    "memory_automation",
    "execution",
    "firmware",
}


def test_generation_package_has_no_external_or_protected_imports() -> None:
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name.split(".")[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            assert not FORBIDDEN.intersection(names), (path, names)


def test_generation_source_has_no_mutation_or_execution_symbols() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in PACKAGE.rglob("*.py")
    ).lower()
    for forbidden in (
        "subprocess",
        "os.system",
        "git ",
        "flash(",
        "build(",
        "execute(",
        "write(",
    ):
        assert forbidden not in source
