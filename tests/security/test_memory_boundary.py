from pathlib import Path


def test_memory_automation_has_no_external_access_imports() -> None:
    root = Path("src/embedded_copilot/memory_automation")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = ("subprocess", "socket", "httpx", "requests", "sqlite3", "os.", "Path(")
    assert not any(token in source for token in forbidden)


def test_knowledge_writer_has_no_provider_or_agent_dependency() -> None:
    root = Path("src/embedded_copilot/knowledge_writer")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "model_runtime" not in source
    assert "rag" not in source.lower()
    assert "agent" not in source.lower()

