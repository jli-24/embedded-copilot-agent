import ast
from pathlib import Path


ROOTS = (
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "contracts.py",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "parser.py",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "service.py",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "factory.py",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "exceptions.py",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "hardware_design"
    / "adapters",
    Path(__file__).parents[2] / "src" / "embedded_copilot" / "hardware_review",
    Path(__file__).parents[2]
    / "src"
    / "embedded_copilot"
    / "api"
    / "hardware_v22_routes.py",
)
FORBIDDEN = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "sqlite3",
    "os",
    "pathlib",
    "shutil",
    "tool_adapter",
    "workspace_runtime",
    "workspace_projection",
    "autonomous_loop",
    "memory_automation",
    "knowledge_writer",
    "HardwareAgent",
    "PCBAgent",
    "SchematicAgent",
    "LayoutAgent",
    "BOMAgent",
}


def test_v22_layers_have_no_external_or_mutating_dependencies() -> None:
    paths = [
        path
        for root in ROOTS
        for path in (root.rglob("*.py") if root.is_dir() else (root,))
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert (
                    not {alias.name.split(".")[0] for alias in node.names} & FORBIDDEN
                ), path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN, path
