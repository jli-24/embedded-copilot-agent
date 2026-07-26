from __future__ import annotations

import ast
import inspect
from pathlib import Path

from embedded_copilot.vision_runtime import VisionPort, VisionRequest

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
VISION_RUNTIME = SRC / "vision_runtime"
LEGACY_VISION = SRC / "vision"
API_ROUTES = SRC / "api" / "copilot_routes.py"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"
RUNTIME_COMPOSITION = VISION_RUNTIME / "composition" / "runtime.py"
BOUNDARY_PATHS = (
    SRC / "conversation",
    SRC / "experience",
    SRC / "copilot",
    SRC / "services",
    SRC / "api",
)
INTERNAL_PREFIXES = (
    "embedded_copilot.vision_runtime.providers",
    "embedded_copilot.vision_runtime.routing",
    "embedded_copilot.vision_runtime.gateway",
    "embedded_copilot.vision_runtime.health",
    "embedded_copilot.vision_runtime.composition",
)
CONCRETE_NAMES = {
    "OllamaVisionProvider",
    "UnavailableVisionProvider",
    "VisionProviderRegistry",
    "VisionRouter",
    "ReferenceVisionPort",
}
FORBIDDEN_MODULES = {
    "fastapi",
    "starlette",
    "streamlit",
    "openai",
    "anthropic",
    "sqlalchemy",
    "sqlite3",
    "chromadb",
    "langgraph",
    "shelve",
}
FORBIDDEN_SEGMENTS = {
    "agents",
    "hardware_design",
    "artifact",
    "decision",
    "evidence",
    "approval",
    "database",
    "persistence",
    "scheduler",
    "websocket",
}
FORBIDDEN_PAYLOAD_NAMES = {
    "bytes",
    "binary",
    "base64",
    "path",
    "content",
    "image_bytes",
    "file_content",
    "absolute_path",
    "local_path",
    "file_path",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.py")))


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def _attribute_parts(value: ast.expr) -> tuple[str, ...]:
    if isinstance(value, ast.Name):
        return (value.id,)
    if isinstance(value, ast.Attribute):
        return (*_attribute_parts(value.value), value.attr)
    return ()


def _factory_call_names(tree: ast.Module) -> tuple[str, ...]:
    direct_names: set[str] = set()
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "embedded_copilot.vision_runtime":
                    module_names.add(alias.asname or alias.name.split(".", 1)[0])
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module == "embedded_copilot.vision_runtime"
        ):
            direct_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "create_vision_runtime"
            )
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in direct_names:
            calls.append(node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_vision_runtime"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_names
        ):
            calls.append(node.func.attr)
    return tuple(calls)


def _runtime_violations(tree: ast.Module) -> tuple[str, ...]:
    violations: list[str] = []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for module in _imported_modules(tree):
        parts = set(module.split("."))
        if module.split(".", 1)[0] in FORBIDDEN_MODULES:
            violations.append(f"forbidden import: {module}")
        if parts & FORBIDDEN_SEGMENTS:
            violations.append(f"forbidden ownership import: {module}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "__import__",
                "eval",
                "exec",
                "import_module",
            }:
                violations.append(f"dynamic call: {node.func.id}")
            if isinstance(node.func, ast.Attribute):
                parts = tuple(
                    part.casefold().lstrip("_") for part in _attribute_parts(node.func)
                )
                if (
                    parts
                    and parts[-1] in {"create", "update", "delete", "transition"}
                    and set(parts[:-1])
                    & {"artifact", "decision", "evidence", "approval"}
                ):
                    violations.append(f"lifecycle call: {'.'.join(parts)}")
                if node.func.attr == "AsyncClient":
                    parent = parents.get(node)
                    while parent is not None and not isinstance(
                        parent,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    ):
                        parent = parents.get(parent)
                    if parent is None:
                        violations.append("module-level HTTP client")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name.casefold().lstrip("_")
            if name in {"stream", "streaming", "websocket", "scheduler", "cache"}:
                violations.append(f"forbidden runtime feature: {name}")
        if isinstance(node, ast.arg):
            name = node.arg.casefold().lstrip("_")
            if name in FORBIDDEN_PAYLOAD_NAMES:
                violations.append(f"forbidden payload argument: {name}")
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id.casefold().lstrip("_")
            if name in FORBIDDEN_PAYLOAD_NAMES:
                violations.append(f"forbidden payload field: {name}")
        if isinstance(node, ast.keyword) and node.arg:
            name = node.arg.casefold().lstrip("_")
            if name in FORBIDDEN_PAYLOAD_NAMES:
                violations.append(f"forbidden payload keyword: {name}")
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and key.value.casefold() == "stream"
                    and not (isinstance(value, ast.Constant) and value.value is False)
                ):
                    violations.append("streaming request enabled")
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and key.value.casefold() in FORBIDDEN_PAYLOAD_NAMES
                ):
                    violations.append(f"forbidden payload key: {key.value}")
    return tuple(violations)


def test_api_route_imports_only_public_vision_runtime_contracts() -> None:
    for module in _imported_modules(_tree(API_ROUTES)):
        assert not module.startswith("embedded_copilot.vision_runtime."), module


def test_vision_runtime_is_framework_independent_and_secure() -> None:
    for path in _python_files(VISION_RUNTIME):
        assert _runtime_violations(_tree(path)) == (), path


def test_only_application_bootstrap_constructs_production_vision_runtime() -> None:
    callers = [
        path
        for path in _python_files(SRC)
        if not path.is_relative_to(VISION_RUNTIME) and _factory_call_names(_tree(path))
    ]
    compose_callers = [
        path
        for path in _python_files(SRC)
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and _attribute_parts(node.func) == ("VisionRuntime", "_compose")
            for node in ast.walk(_tree(path))
        )
    ]

    assert callers == [CONSTRUCTION_ROOT]
    assert compose_callers == [RUNTIME_COMPOSITION]


def test_business_modules_do_not_import_concrete_vision_runtime_internals() -> None:
    for boundary in BOUNDARY_PATHS:
        for path in _python_files(boundary):
            tree = _tree(path)
            for module in _imported_modules(tree):
                assert not module.startswith(INTERNAL_PREFIXES), path
            for node in ast.walk(tree):
                if path != CONSTRUCTION_ROOT and isinstance(
                    node,
                    (ast.Name, ast.Attribute),
                ):
                    name = node.id if isinstance(node, ast.Name) else node.attr
                    assert name not in CONCRETE_NAMES | {
                        "VisionRuntime",
                        "create_vision_runtime",
                    }, path


def test_vision_contracts_are_reference_only_and_model_agnostic() -> None:
    assert tuple(VisionRequest.model_fields) == (
        "session_id",
        "reference_id",
        "image_type",
        "instruction_summary",
    )
    assert not set(VisionRequest.model_fields) & FORBIDDEN_PAYLOAD_NAMES
    assert not set(VisionRequest.model_fields) & {
        "model",
        "provider",
        "endpoint",
        "credential",
    }
    assert tuple(inspect.signature(VisionPort.analyze).parameters) == (
        "self",
        "request",
    )


def test_security_gate_rejects_alias_and_attribute_bypasses() -> None:
    internal_import = ast.parse(
        "import embedded_copilot.vision_runtime.providers as providers"
    )
    factory_alias = ast.parse(
        "import embedded_copilot.vision_runtime as vr\n"
        "vr.create_vision_runtime(settings, repository)"
    )

    assert any(
        module.startswith(INTERNAL_PREFIXES)
        for module in _imported_modules(internal_import)
    )
    assert _factory_call_names(factory_alias) == ("create_vision_runtime",)


def test_security_gate_rejects_payload_lifecycle_and_runtime_bypasses() -> None:
    mutants = (
        "image_bytes: bytes\n",
        "def analyze(*, file_content: str): pass\n",
        "payload = {'base64': 'unsafe'}\n",
        "self._artifact.update()\n",
        "client = httpx.AsyncClient()\n",
        "payload = {'stream': True}\n",
        "import sqlite3\n",
        "import streamlit\n",
    )

    for source in mutants:
        assert _runtime_violations(ast.parse(source)), source


def test_legacy_vision_runtime_ownership_is_removed() -> None:
    assert not tuple(LEGACY_VISION.glob("*.py"))
