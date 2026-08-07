from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path

from embedded_copilot.engineering_knowledge.models import EngineeringGraphSnapshot
from embedded_copilot.engineering_memory import (
    ApprovedEngineeringMemory,
    ApprovedMemoryProjection,
)

from .contracts import (
    GraphMarkdownArtifact,
    KnowledgeWriteResult,
    KnowledgeWriteStatus,
    MarkdownArtifact,
    artifact_from_approved_graph_snapshot,
    artifact_from_approved_memory,
    artifact_from_approved_projection,
)
from .markdown import render_graph_markdown, render_markdown


class FileKnowledgeWriter:
    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def write(self, artifact: MarkdownArtifact) -> KnowledgeWriteResult:
        try:
            if type(artifact) is not MarkdownArtifact:
                raise TypeError
            checked = MarkdownArtifact.model_validate(copy.deepcopy(artifact))
            return self._write_file(
                relative_path=checked.relative_path,
                content=render_markdown(checked).encode("utf-8"),
                memory_id=checked.memory_id,
                temporary_prefix=".memory-",
            )
        except Exception:  # noqa: BLE001
            memory_id = artifact.memory_id if isinstance(artifact, MarkdownArtifact) else "rejected"
            return KnowledgeWriteResult(
                status=KnowledgeWriteStatus.REJECTED,
                memory_id=memory_id,
                event_type=None,
                message="Knowledge artifact was rejected.",
            )

    def _write_file(
        self,
        *,
        relative_path: str,
        content: bytes,
        memory_id: str,
        temporary_prefix: str,
    ) -> KnowledgeWriteResult:
        target = (self._root / relative_path).resolve()
        allowed = (self._root / "docs" / "knowledge").resolve()
        if (
            allowed not in target.parents
            or target == allowed
            or (self._root / "docs").is_symlink()
            or (self._root / "docs" / "knowledge").is_symlink()
            or target.parent.is_symlink()
        ):
            raise ValueError
        if target.exists() and target.is_symlink():
            raise ValueError
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        fd, temporary = tempfile.mkstemp(
            prefix=temporary_prefix, suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return KnowledgeWriteResult(
            status=KnowledgeWriteStatus.UPDATED if existed else KnowledgeWriteStatus.CREATED,
            memory_id=memory_id,
            event_type=("MEMORY_UPDATED" if existed else "MEMORY_CREATED"),
            message="Knowledge artifact written.",
        )

    def write_graph_artifact(
        self, artifact: GraphMarkdownArtifact
    ) -> KnowledgeWriteResult:
        try:
            checked = GraphMarkdownArtifact.model_validate(copy.deepcopy(artifact))
            return self._write_file(
                relative_path=checked.relative_path,
                content=render_graph_markdown(checked).encode("utf-8"),
                memory_id=checked.node_id,
                temporary_prefix=".graph-",
            )
        except Exception:  # noqa: BLE001
            memory_id = artifact.node_id if isinstance(artifact, GraphMarkdownArtifact) else "rejected"
            return KnowledgeWriteResult(
                status=KnowledgeWriteStatus.REJECTED,
                memory_id=memory_id,
                event_type=None,
                message="Knowledge graph artifact was rejected.",
            )

    def write_approved_projection(
        self, projection: ApprovedMemoryProjection | ApprovedEngineeringMemory
    ) -> KnowledgeWriteResult:
        if type(projection) is ApprovedEngineeringMemory:
            return self.write_approved_memory(projection)
        artifact = artifact_from_approved_projection(projection)
        return self.write(artifact)

    def write_approved_memory(
        self, memory: ApprovedEngineeringMemory
    ) -> KnowledgeWriteResult:
        return self.write(artifact_from_approved_memory(memory))

    def write_approved_graph_projection(
        self, snapshot: EngineeringGraphSnapshot
    ) -> tuple[KnowledgeWriteResult, ...]:
        try:
            artifacts = artifact_from_approved_graph_snapshot(snapshot)
        except Exception:  # noqa: BLE001
            return (
                KnowledgeWriteResult(
                    status=KnowledgeWriteStatus.REJECTED,
                    memory_id="graph",
                    event_type=None,
                    message="Knowledge graph projection was rejected.",
                ),
            )
        return tuple(self.write_graph_artifact(artifact) for artifact in artifacts)
