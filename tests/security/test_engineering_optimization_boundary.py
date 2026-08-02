from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path("src/embedded_copilot/engineering_optimization")


def test_optimization_package_has_no_execution_or_io_boundary() -> None:
    forbidden_imports = {
        "subprocess",
        "os",
        "pathlib",
        "socket",
        "requests",
        "httpx",
        "sqlite3",
        "threading",
        "asyncio",
    }
    forbidden_roots = (
        "embedded_copilot.execution_runtime",
        "embedded_copilot.tool_runtime",
        "embedded_copilot.workspace_runtime",
        "embedded_copilot.supervisor",
    )
    typed_upstream_roots = (
        "embedded_copilot.engineering_artifacts",
        "embedded_copilot.engineering_execution",
        "embedded_copilot.engineering_feedback",
        "embedded_copilot.engineering_validation",
    )
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.split(".")[0] in forbidden_imports
                    for alias in node.names
                )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_imports
                assert not node.module.startswith(forbidden_roots)
                if node.module.startswith(typed_upstream_roots):
                    assert path.as_posix().endswith("integration/inputs.py")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "build",
                    "flash",
                    "debug",
                    "execute",
                    "write_text",
                    "write_bytes",
                    "model_dump_json",
                }
