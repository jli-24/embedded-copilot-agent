from __future__ import annotations

import os
import stat
from pathlib import Path

from embedded_copilot.file_runtime.contracts import (
    FileReference,
    FileReferenceCatalog,
    FileReferenceRequest,
    FileType,
)
from embedded_copilot.file_runtime.exceptions import (
    FileReferenceConflict,
    FileReferenceNotFound,
    FileRuntimeError,
    FileRuntimeUnavailable,
)

_SOURCE_SUFFIXES = frozenset({".c", ".cpp", ".h", ".py"})
_TEXT_SUFFIXES = frozenset({".md", ".txt", ".log", ".json"})

FileSnapshot = tuple[int, int, int, int, int, int]


class ResolvedFile:
    __slots__ = ("descriptor", "path", "reference", "snapshots")

    def __init__(
        self,
        reference: FileReference,
        path: Path,
        snapshots: tuple[tuple[Path, FileSnapshot], ...],
        descriptor: int,
    ) -> None:
        self.reference = reference
        self.path = path
        self.snapshots = snapshots
        self.descriptor = descriptor


class RootedFileResolver:
    __slots__ = ("_catalog", "_root", "_root_snapshot")

    def __init__(
        self,
        root: str | Path,
        catalog: FileReferenceCatalog,
    ) -> None:
        try:
            candidate = Path(root)
            if candidate.is_symlink() or not candidate.is_dir():
                raise ValueError("invalid root")
            resolved = candidate.resolve(strict=True)
            root_snapshot = _file_snapshot(resolved.lstat())
        except Exception:
            raise FileRuntimeUnavailable() from None
        self._root = resolved
        self._root_snapshot = root_snapshot
        self._catalog = catalog

    def resolve(self, request: FileReferenceRequest) -> ResolvedFile:
        try:
            reference = self._catalog.resolve(request.session_id, request.file_id)
        except Exception:
            raise FileRuntimeUnavailable() from None
        if reference is None:
            raise FileReferenceNotFound()
        if not isinstance(reference, FileReference):
            raise FileReferenceConflict()
        snapshot = reference.model_copy(deep=True)
        if (
            snapshot.session_id.casefold() != request.session_id.casefold()
            or snapshot.file_id.casefold() != request.file_id.casefold()
            or (
                request.file_type is not FileType.UNKNOWN
                and request.file_type is not snapshot.document_type
            )
        ):
            raise FileReferenceConflict()

        candidate = self._root / snapshot.relative_path
        if candidate.name != snapshot.basename:
            raise FileReferenceConflict()
        try:
            relative_parts = candidate.relative_to(self._root).parts
        except ValueError:
            raise FileReferenceConflict() from None
        cursor = self._root
        snapshots: list[tuple[Path, FileSnapshot]] = []
        try:
            current_root_snapshot = _file_snapshot(self._root.lstat())
            if current_root_snapshot != self._root_snapshot:
                raise FileReferenceConflict()
            snapshots.append((self._root, self._root_snapshot))
            for part in relative_parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise FileReferenceConflict()
                snapshots.append((cursor, _file_snapshot(cursor.lstat())))
            resolved = candidate.resolve(strict=True)
        except FileRuntimeError:
            raise
        except FileNotFoundError:
            raise FileReferenceNotFound() from None
        except Exception:
            raise FileReferenceConflict() from None
        if not resolved.is_relative_to(self._root):
            raise FileReferenceConflict()
        if resolved != candidate or not snapshots:
            raise FileReferenceConflict()
        try:
            if _file_snapshot(resolved.lstat()) != snapshots[-1][1]:
                raise FileReferenceConflict()
        except FileRuntimeError:
            raise
        except Exception:
            raise FileReferenceConflict() from None
        if not _suffix_matches(snapshot.document_type, resolved.suffix):
            raise FileReferenceConflict()

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(resolved, flags)
        except FileNotFoundError:
            raise FileReferenceNotFound() from None
        except Exception:
            raise FileReferenceConflict() from None
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or _file_snapshot(opened) != snapshots[-1][1]
            ):
                raise FileReferenceConflict()
        except Exception:
            os.close(descriptor)
            raise
        return ResolvedFile(
            snapshot,
            resolved,
            tuple(snapshots),
            descriptor,
        )


def _suffix_matches(document_type: FileType, suffix: str) -> bool:
    normalized = suffix.casefold()
    if document_type is FileType.SOURCE_CODE:
        return normalized in _SOURCE_SUFFIXES
    if document_type is FileType.TEXT:
        return normalized in _TEXT_SUFFIXES
    if document_type in {FileType.PDF, FileType.DATASHEET}:
        return normalized == ".pdf"
    return False


def _file_snapshot(value: os.stat_result) -> FileSnapshot:
    return (
        value.st_mode,
        value.st_size,
        value.st_dev,
        value.st_ino,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
