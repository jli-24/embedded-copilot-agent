from __future__ import annotations

import ast
import asyncio
import inspect
from pathlib import Path

from embedded_copilot.datasheet_runtime import (
    DatasheetIntelligencePort,
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
)

ROOT = Path(__file__).parents[2]
SRC = ROOT / "src" / "embedded_copilot"
RUNTIME = SRC / "datasheet_runtime"
CONSTRUCTION_ROOT = SRC / "api" / "main.py"
EXPECTED_DIRECTORIES = {
    "composition",
    "contracts",
    "extractors",
    "parser",
    "security",
}
FORBIDDEN_IMPORTS = {
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
}
FORBIDDEN_RUNTIME_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.rag",
    "embedded_copilot.intelligence",
    "embedded_copilot.model_runtime",
    "embedded_copilot.vision_runtime",
    "embedded_copilot.engineering",
    "embedded_copilot.hardware_design",
)
FORBIDDEN_OPERATIONS = {
    "write",
    "patch",
    "execute",
    "generate",
    "generate_code",
    "modify_file",
    "execute_command",
    "change_configuration",
    "save",
    "persist",
    "approve",
    "promote",
    "to_engineering_fact",
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


class _ReadOnlyDatasheetPort:
    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        return DatasheetResponse(summary=DatasheetSummary(file_id=request.file_id))


class FutureCodingAgent:
    __slots__ = ("_datasheet_port",)

    def __init__(self, datasheet_port: DatasheetIntelligencePort) -> None:
        self._datasheet_port = datasheet_port

    async def analyze(self) -> DatasheetResponse:
        return await self._datasheet_port.analyze(
            DatasheetRequest(
                session_id="session:1",
                file_id="file:1",
                instruction_summary="Extract unverified candidates.",
            )
        )


def test_datasheet_runtime_has_fixed_framework_independent_boundary() -> None:
    assert {
        path.name for path in RUNTIME.iterdir() if path.is_dir()
    } >= EXPECTED_DIRECTORIES
    for path in _python_files(RUNTIME):
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
                    "open",
                }, path
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_OPERATIONS, path


def test_only_api_bootstrap_constructs_datasheet_runtime() -> None:
    callers: list[Path] = []
    for path in _python_files(SRC):
        if path.is_relative_to(RUNTIME):
            continue
        for node in ast.walk(_tree(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "create_datasheet_runtime"
            ):
                callers.append(path)

    assert callers == [CONSTRUCTION_ROOT]


def test_datasheet_routes_do_not_import_parser_or_extractors() -> None:
    routes = SRC / "api" / "copilot_routes.py"

    assert all(
        not module.startswith(
            (
                "embedded_copilot.datasheet_runtime.parser",
                "embedded_copilot.datasheet_runtime.extractors",
            )
        )
        for module in _imports(_tree(routes))
    )


def test_future_coding_agent_receives_candidates_without_fact_capability() -> None:
    consumer = FutureCodingAgent(_ReadOnlyDatasheetPort())

    response = asyncio.run(consumer.analyze())

    assert response.summary.candidate_semantics == "unverified"
    assert tuple(inspect.signature(DatasheetIntelligencePort.analyze).parameters) == (
        "self",
        "request",
    )
    for forbidden in (
        *FORBIDDEN_OPERATIONS,
        "FileWritePort",
        "extraction_port",
        "EngineeringFact",
        "Evidence",
        "Decision",
        "Artifact",
    ):
        assert not hasattr(consumer, forbidden)
        assert not hasattr(consumer._datasheet_port, forbidden)
        assert not hasattr(DatasheetIntelligencePort, forbidden)
