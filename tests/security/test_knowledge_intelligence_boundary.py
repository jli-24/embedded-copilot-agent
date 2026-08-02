from __future__ import annotations

import ast
import inspect
from pathlib import Path

import embedded_copilot.knowledge.intelligence as intelligence

PACKAGE = Path("src/embedded_copilot/knowledge/intelligence")
FORBIDDEN_IMPORT_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.api",
    "embedded_copilot.supervisor",
    "embedded_copilot.tool_runtime",
    "fastapi",
    "httpx",
    "langgraph",
    "neo4j",
    "requests",
    "starlette",
    "streamlit",
)
FORBIDDEN_CALLS = {
    "__import__",
    "eval",
    "exec",
    "open",
}
FORBIDDEN_ATTRIBUTES = {
    "execute",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
}


def _imports(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(item.name for item in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def test_knowledge_intelligence_has_no_control_or_transport_dependencies() -> None:
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            for imported in _imports(node):
                assert not imported.startswith(FORBIDDEN_IMPORT_PREFIXES), (
                    path,
                    imported,
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, path
            if isinstance(node, ast.Attribute):
                assert node.attr not in FORBIDDEN_ATTRIBUTES, (path, node.attr)
        lowered = source.casefold()
        for token in (
            "supervisorplan",
            "agent_name",
            "tool_call",
            "autonomous",
            "neo4j",
            "browser",
            "download",
        ):
            assert token not in lowered, (path, token)


def test_public_facade_and_port_are_narrow() -> None:
    assert {
        name
        for name, value in intelligence.KnowledgeIntelligenceRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"knowledge_port"}
    assert {
        name
        for name, value in intelligence.KnowledgeIntelligencePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {
        "analyze_datasheet",
        "project_graph",
        "project_memory_candidate",
        "query_graph",
        "retrieve",
    }
    assert tuple(
        inspect.signature(
            intelligence.KnowledgeIntelligencePort.retrieve
        ).parameters
    ) == ("self", "request")
    for internal in (
        "DeterministicKnowledgeVerifier",
        "KnowledgeGraphProjector",
        "KnowledgeMemoryBridge",
    ):
        assert not hasattr(intelligence, internal)
