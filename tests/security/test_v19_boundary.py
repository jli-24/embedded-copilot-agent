from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"
FORBIDDEN_IMPORTS = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "sqlite3",
    "gitpython",
}
FORBIDDEN_NAMES = {
    "hardware_validation_agent",
    "hardware_agent",
    "device_agent",
    "flash_agent",
    "validation_agent",
    "repair_agent",
}


def test_v19_packages_are_projection_boundaries() -> None:
    paths = [
        ROOT / "device_runtime",
        ROOT / "hardware_observation",
        ROOT / "validation_loop",
        ROOT / "toolchain" / "flash.py",
        ROOT / "toolchain" / "adapters" / "flash.py",
    ]
    for path in paths:
        files = [path] if path.is_file() else list(path.rglob("*.py"))
        for file in files:
            lowered = str(file).lower().replace("\\", "/")
            assert not any(name in lowered for name in FORBIDDEN_NAMES)
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all(
                        alias.name.split(".")[0].lower() not in FORBIDDEN_IMPORTS
                        for alias in node.names
                    )
                if isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[
                        0
                    ].lower() not in FORBIDDEN_IMPORTS
