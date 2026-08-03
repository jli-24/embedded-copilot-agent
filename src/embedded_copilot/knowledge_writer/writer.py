from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path

from .contracts import KnowledgeWriteResult, KnowledgeWriteStatus, MarkdownArtifact
from .markdown import render_markdown


class FileKnowledgeWriter:
    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def write(self, artifact: MarkdownArtifact) -> KnowledgeWriteResult:
        try:
            if type(artifact) is not MarkdownArtifact:
                raise TypeError
            checked = MarkdownArtifact.model_validate(copy.deepcopy(artifact))
            target = (self._root / checked.relative_path).resolve()
            allowed = (self._root / "docs" / "knowledge").resolve()
            if (
                allowed not in target.parents
                or target == allowed
                or (self._root / "docs").is_symlink()
                or (self._root / "docs" / "knowledge").is_symlink()
            ):
                raise ValueError
            if target.exists() and target.is_symlink():
                raise ValueError
            target.parent.mkdir(parents=True, exist_ok=True)
            content = render_markdown(checked).encode("utf-8")
            existed = target.exists()
            fd, temporary = tempfile.mkstemp(prefix=".memory-", suffix=".tmp", dir=target.parent)
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
                memory_id=checked.memory_id,
                event_type=("MEMORY_UPDATED" if existed else "MEMORY_CREATED"),
                message="Knowledge artifact written.",
            )
        except Exception:
            memory_id = artifact.memory_id if isinstance(artifact, MarkdownArtifact) else "rejected"
            return KnowledgeWriteResult(
                status=KnowledgeWriteStatus.REJECTED,
                memory_id=memory_id,
                event_type=None,
                message="Knowledge artifact was rejected.",
            )
