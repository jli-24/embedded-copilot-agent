import ast
from pathlib import Path


ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot" / "tool_adapter"
FORBIDDEN = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "sqlite3",
    "os",
    "pathlib",
    "shutil",
    "autonomous_loop",
    "approval_gate",
    "reasoning",
    "supervisor",
    "memory_automation",
    "knowledge_writer",
    "BuildAgent",
    "FlashAgent",
    "DeviceAgent",
    "DebugAgent",
    "ToolAgent",
}


def test_tool_adapter_has_no_external_or_reverse_runtime_imports() -> None:
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                assert not names & FORBIDDEN, path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN, path
