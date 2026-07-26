from __future__ import annotations

import ast
import inspect
from pathlib import Path

from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.schemas.model import ModelRequest

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
MODEL_RUNTIME = SRC / "model_runtime"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"
BOUNDARY_PATHS = (
    SRC / "conversation",
    SRC / "experience",
    SRC / "copilot",
    SRC / "services",
    SRC / "api",
)
INTERNAL_MODULE_PREFIXES = (
    "embedded_copilot.model_runtime.providers",
    "embedded_copilot.model_runtime.registry",
    "embedded_copilot.model_runtime.routing",
    "embedded_copilot.model_runtime.gateway",
    "embedded_copilot.model_runtime.health",
    "embedded_copilot.model_runtime.composition",
)
CONCRETE_RUNTIME_NAMES = {
    "OllamaProvider",
    "ModelGateway",
    "ModelRouter",
    "ProviderRegistry",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.py")))


def test_model_runtime_is_framework_independent_and_has_no_dynamic_bypass() -> None:
    forbidden_modules = {
        "fastapi",
        "starlette",
        "streamlit",
        "sqlalchemy",
        "sqlite3",
        "langgraph",
        "openai",
    }
    forbidden_calls = {"__import__", "eval", "exec"}

    for path in _python_files(MODEL_RUNTIME):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                assert (
                    not {alias.name.split(".", 1)[0] for alias in node.names}
                    & forbidden_modules
                ), path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".", 1)[0] not in forbidden_modules, path
                assert node.module != "importlib", path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, path


def test_business_and_api_modules_do_not_import_model_runtime_internals() -> None:
    for boundary in BOUNDARY_PATHS:
        for path in _python_files(boundary):
            tree = _tree(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith(INTERNAL_MODULE_PREFIXES), path
                    if path != CONSTRUCTION_ROOT:
                        assert not (
                            node.module == "embedded_copilot.model_runtime"
                            and any(
                                alias.name in {"ModelRuntime", "create_model_runtime"}
                                for alias in node.names
                            )
                        ), path
                if isinstance(node, ast.Name):
                    assert node.id not in CONCRETE_RUNTIME_NAMES, path


def test_only_application_bootstrap_constructs_production_model_runtime() -> None:
    callers: list[Path] = []
    for path in _python_files(SRC):
        if path.is_relative_to(MODEL_RUNTIME):
            continue
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_model_runtime"
            ):
                callers.append(path)

    assert callers == [CONSTRUCTION_ROOT]


def test_model_request_and_reasoning_port_remain_model_agnostic() -> None:
    assert tuple(ModelRequest.model_fields) == (
        "task_type",
        "input_type",
        "context_ids",
    )
    signature = inspect.signature(ReasoningPort.reason)
    assert tuple(signature.parameters) == (
        "self",
        "user_message_summary",
        "context_summaries",
        "task_intent",
    )
    assert all(
        forbidden not in signature.parameters
        for forbidden in (
            "model",
            "provider",
            "endpoint",
            "capability",
            "credential",
        )
    )


def test_model_runtime_does_not_import_engineering_lifecycle_owners() -> None:
    forbidden_segments = {
        "agents",
        "hardware_design",
        "approval",
        "decision",
        "evidence",
        "database",
        "cache",
        "scheduler",
        "websocket",
    }

    for path in _python_files(MODEL_RUNTIME):
        for node in ast.walk(_tree(path)):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not set(alias.name.split(".")) & forbidden_segments, path
            if module:
                assert not set(module.split(".")) & forbidden_segments, path
