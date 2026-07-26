from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

from embedded_copilot.file_runtime import (
    DocumentSummary,
    FileIntelligencePort,
    FileReferenceCatalog,
    FileReferenceRequest,
)
from embedded_copilot.file_runtime.contracts import Extractor

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
FILE_RUNTIME = SRC / "file_runtime"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"
BOUNDARY_PATHS = (
    SRC / "api",
    SRC / "conversation",
    SRC / "experience",
    SRC / "copilot",
    SRC / "services",
)
INTERNAL_PREFIX = "embedded_copilot.file_runtime."
FORBIDDEN_IMPORTS = {
    "fastapi",
    "starlette",
    "streamlit",
    "langgraph",
    "sqlalchemy",
    "sqlite3",
    "chromadb",
    "subprocess",
    "tempfile",
}
FORBIDDEN_RUNTIME_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.intelligence",
    "embedded_copilot.model_runtime",
    "embedded_copilot.rag",
    "embedded_copilot.vision_runtime",
    "embedded_copilot.multimodal",
    "embedded_copilot.experience",
    "embedded_copilot.copilot.workspace",
)
FORBIDDEN_OPERATIONS = {
    "write",
    "edit_file",
    "patch_file",
    "save_file",
    "generate_code",
    "execute",
    "change_configuration",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.rglob("*.py")))


def _imports(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_file_runtime_has_fixed_framework_independent_repository_boundary() -> None:
    expected_directories = {
        "composition",
        "contracts",
        "extractors",
        "reader",
        "security",
    }

    assert expected_directories.issubset(
        {path.name for path in FILE_RUNTIME.iterdir() if path.is_dir()}
    )
    for path in _python_files(FILE_RUNTIME):
        tree = _tree(path)
        for module in _imports(tree):
            assert module.split(".", 1)[0] not in FORBIDDEN_IMPORTS, path
            assert not module.startswith(FORBIDDEN_RUNTIME_PREFIXES), path
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {
                    "__import__",
                    "eval",
                    "exec",
                    "compile",
                }, path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_OPERATIONS, path
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
            ):
                mode = node.args[1] if len(node.args) > 1 else None
                if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
                    assert not set(mode.value) & set("wax+"), path


def test_only_api_bootstrap_constructs_file_runtime() -> None:
    callers: list[Path] = []
    for path in _python_files(SRC):
        if path.is_relative_to(FILE_RUNTIME):
            continue
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_file_runtime"
            ):
                callers.append(path)

    assert callers == [CONSTRUCTION_ROOT]


def test_business_and_routes_do_not_import_file_runtime_internals() -> None:
    for boundary in BOUNDARY_PATHS:
        for path in _python_files(boundary):
            for module in _imports(_tree(path)):
                assert not module.startswith(INTERNAL_PREFIX), path


def test_file_catalog_adapter_does_not_depend_on_workspace_ownership() -> None:
    adapter = SRC / "api" / "file_reference_catalog.py"

    assert all(
        not module.startswith("embedded_copilot.copilot")
        for module in _imports(_tree(adapter))
    )


def test_file_contracts_are_read_only_and_content_free() -> None:
    assert tuple(inspect.signature(FileIntelligencePort.analyze).parameters) == (
        "self",
        "request",
    )
    assert {
        name
        for name, value in FileReferenceCatalog.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"resolve"}
    assert get_type_hints(Extractor.extract)["return"] is DocumentSummary
    assert tuple(FileReferenceRequest.model_fields) == (
        "session_id",
        "file_id",
        "file_type",
        "instruction_summary",
    )
    assert not set(DocumentSummary.model_fields) & {
        "content",
        "text",
        "markdown",
        "code",
        "keywords",
        "entities",
        "chips",
        "interfaces",
        "pins",
        "embedding",
        "vector",
    }
    assert DocumentSummary.model_config["frozen"] is True
    assert DocumentSummary.model_config["extra"] == "forbid"


def test_legacy_file_intelligence_ownership_is_removed() -> None:
    assert not tuple((SRC / "file_intelligence").glob("*.py"))
