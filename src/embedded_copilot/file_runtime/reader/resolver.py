from __future__ import annotations

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


class ResolvedFile:
    __slots__ = ("reference", "path")

    def __init__(self, reference: FileReference, path: Path) -> None:
        self.reference = reference
        self.path = path


class RootedFileResolver:
    __slots__ = ("_catalog", "_root")

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
        except Exception:
            raise FileRuntimeUnavailable() from None
        self._root = resolved
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
        try:
            for part in relative_parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise FileReferenceConflict()
                cursor.lstat()
            resolved = candidate.resolve(strict=True)
        except FileRuntimeError:
            raise
        except FileNotFoundError:
            raise FileReferenceNotFound() from None
        except Exception:
            raise FileReferenceConflict() from None
        if not resolved.is_relative_to(self._root):
            raise FileReferenceConflict()
        if not _suffix_matches(snapshot.document_type, resolved.suffix):
            raise FileReferenceConflict()
        return ResolvedFile(snapshot, resolved)


def _suffix_matches(document_type: FileType, suffix: str) -> bool:
    normalized = suffix.casefold()
    if document_type is FileType.SOURCE_CODE:
        return normalized in _SOURCE_SUFFIXES
    if document_type is FileType.TEXT:
        return normalized in _TEXT_SUFFIXES
    if document_type in {FileType.PDF, FileType.DATASHEET}:
        return normalized == ".pdf"
    return False
