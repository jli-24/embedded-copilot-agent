import ast
from pathlib import Path


def test_intelligence_packages_have_no_external_or_mutating_boundaries() -> None:
    roots = (
        Path("src/embedded_copilot/engineering_intelligence"),
        Path("src/embedded_copilot/datasheet_agent"),
        Path("src/embedded_copilot/web_research_agent"),
    )
    forbidden = (
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "sqlite3",
        "pathlib",
        "model_runtime",
        "reasoning_runtime",
        "supervisor",
        "rag",
    )
    forbidden_names = {
        "open",
        "getattr",
        "setattr",
        "exec",
        "eval",
        "compile",
        "__import__",
        "import_module",
    }
    files = tuple(path for root in roots for path in root.rglob("*.py"))
    assert files
    for path in files:
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        assert not any(token.lower() in lowered for token in forbidden), path
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else None
                assert name not in forbidden_names, path

