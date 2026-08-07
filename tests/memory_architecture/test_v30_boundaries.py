import ast
from pathlib import Path


def _imports(root: Path) -> tuple[str, ...]:
    values: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                values.append(node.module)
    return tuple(values)


def test_api_memory_route_depends_on_application_service_only() -> None:
    source = Path("src/embedded_copilot/api/memory_routes.py").read_text(
        encoding="utf-8"
    )
    imports = _imports(Path("src/embedded_copilot/api"))
    assert "memory_service" in source
    assert not any(item.startswith("embedded_copilot.knowledge_writer") for item in imports)
    assert not any(item.startswith("embedded_copilot.engineering_memory.store") for item in imports)


def test_knowledge_evolution_and_writer_have_no_reverse_memory_dependencies() -> None:
    knowledge_imports = _imports(Path("src/embedded_copilot/knowledge_evolution"))
    writer_imports = _imports(Path("src/embedded_copilot/knowledge_writer"))
    assert not any("memory_automation" in item for item in knowledge_imports)
    assert not any(item.startswith("embedded_copilot.conversation_memory") for item in writer_imports)
