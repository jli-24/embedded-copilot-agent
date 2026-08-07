from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from embedded_copilot.engineering_memory import ApprovedMemoryProjection
from embedded_copilot.knowledge_writer import (
    artifact_from_approved_projection,
    create_knowledge_writer,
)


def _projection() -> ApprovedMemoryProjection:
    material = {
        "project_id": "project-1",
        "memory_id": "memory-1",
        "record_id": "record-1",
        "memory_type": "ENGINEERING_DECISION",
        "status": "APPROVED",
        "source_reference": "conversation:session-1",
        "source_revision": "sha256:" + "a" * 64,
        "title": "Engineering Decision",
        "summary": "Keep the boundary explicit.",
        "evidence_references": ("conversation:session-1",),
    }
    provisional = ApprovedMemoryProjection.model_construct(
        **material, fingerprint="sha256:" + "0" * 64
    )
    encoded = json.dumps(
        provisional.model_dump(mode="json", exclude={"fingerprint"}),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ApprovedMemoryProjection(
        **material, fingerprint="sha256:" + hashlib.sha256(encoded).hexdigest()
    )


def test_writer_only_consumes_approved_engineering_projection(tmp_path) -> None:
    artifact = artifact_from_approved_projection(_projection())
    result = create_knowledge_writer(tmp_path).write(artifact)
    assert result.status.value == "CREATED"
    assert (tmp_path / artifact.relative_path).exists()


def test_knowledge_writer_has_no_conversation_dependency() -> None:
    root = Path("src/embedded_copilot/knowledge_writer")
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    tree = ast.parse(source)
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    imports.extend(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert not any(item.startswith("embedded_copilot.conversation") for item in imports)
