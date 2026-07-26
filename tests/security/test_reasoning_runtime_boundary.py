from __future__ import annotations

import ast
import inspect
from pathlib import Path

from embedded_copilot.reasoning_runtime import ReasoningPort

ROOT = Path(__file__).parents[2]
RUNTIME = ROOT / "src" / "embedded_copilot" / "reasoning_runtime"
FORBIDDEN_ROOT_IMPORTS = {
    "fastapi",
    "starlette",
    "streamlit",
    "langgraph",
    "langchain",
    "chromadb",
    "sqlalchemy",
    "sqlite3",
    "shelve",
    "subprocess",
    "pathlib",
    "os",
    "socket",
    "requests",
    "httpx",
}
FORBIDDEN_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.model_runtime",
    "embedded_copilot.file_runtime",
    "embedded_copilot.datasheet_runtime",
    "embedded_copilot.vision_runtime",
    "embedded_copilot.rag",
)
FORBIDDEN_OPERATIONS = {
    "write",
    "edit",
    "patch",
    "execute",
    "generate",
    "generate_code",
    "apply",
    "modify",
    "save",
    "persist",
    "flash_firmware",
    "modify_code",
    "change_pid",
    "execute_shell",
    "create_patch",
    "apply_patch",
    "write_workspace",
    "open_terminal",
    "control_vscode",
}
PURE_RULE_FORBIDDEN_IMPORTS = {
    "datetime",
    "os",
    "pathlib",
    "random",
    "secrets",
    "socket",
    "subprocess",
    "time",
    "uuid",
}
TASK_KEYWORDS = {"camera", "wifi", "udp", "pwm", "timer"}


def _python_files(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_reasoning_runtime_has_framework_independent_boundary() -> None:
    for path in _python_files(RUNTIME):
        tree = _tree(path)
        for module in _imports(tree):
            assert module.split(".", 1)[0] not in FORBIDDEN_ROOT_IMPORTS, path
            assert not module.startswith(FORBIDDEN_PREFIXES), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {
                    "__import__",
                    "eval",
                    "exec",
                    "compile",
                    "open",
                }, path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_OPERATIONS, path


class FutureCodingAgent:
    def __init__(self, reasoning: ReasoningPort) -> None:
        self.reasoning = reasoning


class FutureEmbeddedAgent:
    def __init__(self, reasoning: ReasoningPort) -> None:
        self.reasoning = reasoning


def test_future_agents_receive_only_reasoning_analysis() -> None:
    assert tuple(inspect.signature(ReasoningPort.analyze).parameters) == (
        "self",
        "request",
    )
    for consumer in (FutureCodingAgent, FutureEmbeddedAgent):
        hints = inspect.signature(consumer.__init__).parameters
        assert tuple(hints) == ("self", "reasoning")
    for forbidden in FORBIDDEN_OPERATIONS:
        assert not hasattr(ReasoningPort, forbidden)


def test_rules_are_pure_and_cannot_read_task_intent_keywords() -> None:
    rules = RUNTIME / "rules"
    for path in _python_files(rules):
        tree = _tree(path)
        for module in _imports(tree):
            assert module.split(".", 1)[0] not in PURE_RULE_FORBIDDEN_IMPORTS, path
        for node in ast.walk(tree):
            assert not isinstance(node, (ast.Global, ast.Nonlocal)), path
            if isinstance(node, ast.AsyncFunctionDef):
                raise AssertionError(f"rule functions must be synchronous: {path}")
            if isinstance(node, ast.Name):
                assert node.id != "task_intent", path
            if isinstance(node, ast.Attribute):
                assert node.attr != "task_intent", path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                tokens = set(node.value.casefold().replace("_", " ").split())
                assert not tokens & TASK_KEYWORDS, path
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                assert not isinstance(value, (ast.List, ast.Dict, ast.Set)), path
