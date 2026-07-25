from __future__ import annotations

from pathlib import Path


def test_v023_alpha1_release_note_documents_scope_and_boundaries() -> None:
    release_path = Path("docs/release/v0.23.0-alpha1.md")

    assert release_path.is_file()
    release_note = release_path.read_text(encoding="utf-8")
    assert tuple(
        line.removeprefix("## ").strip()
        for line in release_note.splitlines()
        if line.startswith("## ")
    ) == ("Added", "Architecture Boundary", "Validation", "Limitations")
    assert all(
        value in release_note
        for value in (
            "# Embedded Copilot v0.23.0-alpha1",
            "Model Gateway",
            "suggestion-only",
            "provider isolation",
            "`KnowledgeEvidence`",
            "`KnowledgeTrace`",
            "approval staging",
            "process-local",
            "reasoning expiration",
            "`/api/v1/copilot/sessions`",
            "`/api/v1/copilot/sessions/{session_id}/messages`",
            "metadata-only ESP32 handoff",
            "Engineering Artifact lifecycle",
            "Engineering Fact",
            "Decision、Evidence、Approval",
            "Engineering Agent Layer",
            "1242 passed、3 skipped",
            "Ruff passed",
            "v0.23 Black scope passed",
            "compileall passed",
            "GPT/DeepSeek/Ollama",
            "Vision",
            "database persistence",
            "Full UI",
            "EDA/PCB generation",
            "Firmware generation",
            "auto flashing",
        )
    )
