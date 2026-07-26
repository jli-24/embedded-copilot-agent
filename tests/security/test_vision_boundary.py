from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
VISION_RUNTIME = SRC / "vision_runtime"
API_ROUTES = SRC / "api" / "copilot_routes.py"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_api_route_imports_only_public_vision_runtime_contracts() -> None:
    for node in ast.walk(_tree(API_ROUTES)):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(
                "embedded_copilot.vision_runtime."
            ), node.module
