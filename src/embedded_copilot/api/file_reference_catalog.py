from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

from embedded_copilot.file_runtime import (
    FileReference,
    FileReferenceCatalog,
    FileReferenceConflict,
    FileType,
)
from embedded_copilot.multimodal.context import (
    AttachmentBindingNotFound,
    AttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import MultimodalInputType

_SOURCE_SUFFIXES = frozenset({".c", ".cpp", ".h", ".py"})
_TEXT_SUFFIXES = frozenset({".md", ".txt", ".log", ".json"})
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


class CopilotFileReferenceCatalog(FileReferenceCatalog):
    """Read-only projection from Copilot metadata to trusted file references."""

    __slots__ = ("_paths", "_repository")

    def __init__(
        self,
        repository: AttachmentBindingRepository,
        reference_paths: Mapping[tuple[str, str], str | Path],
    ) -> None:
        self._repository = repository
        try:
            copied = copy.deepcopy(dict(reference_paths))
            normalized: dict[tuple[str, str], Path] = {}
            for raw_key, raw_path in copied.items():
                if not isinstance(raw_key, tuple) or len(raw_key) != 2:
                    raise ValueError("invalid reference key")
                session_id = _safe_identifier(raw_key[0], field="session_id")
                file_id = _safe_identifier(raw_key[1], field="file_id")
                key = (session_id.casefold(), file_id.casefold())
                if key in normalized:
                    raise ValueError("duplicate reference")
                normalized[key] = _relative_path(raw_path)
        except Exception:
            raise FileReferenceConflict() from None
        self._paths = normalized

    def resolve(self, session_id: str, file_id: str) -> FileReference | None:
        try:
            session_key = _safe_identifier(
                session_id,
                field="session_id",
            ).casefold()
            file_key = _safe_identifier(file_id, field="file_id").casefold()
            relative_path = self._paths.get((session_key, file_key))
            if relative_path is None:
                return None
            binding = self._repository.get(session_id, file_id)
        except AttachmentBindingNotFound:
            return None
        except Exception:
            raise FileReferenceConflict() from None
        if binding.input.type is not MultimodalInputType.FILE:
            raise FileReferenceConflict()
        document_type = _document_type(binding.basename)
        return FileReference(
            session_id=binding.session_id,
            file_id=binding.input.reference_id,
            basename=binding.basename,
            document_type=document_type,
            size_bytes=binding.size_bytes,
            relative_path=relative_path,
        )


def _relative_path(value: object) -> Path:
    if not isinstance(value, (str, Path)):
        raise ValueError("invalid path")
    raw = str(value)
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw.strip()
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or raw.startswith(("/", "\\"))
        or any(part in {"", ".", ".."} for part in posix.parts)
        or any(part in {"", ".", ".."} for part in windows.parts)
    ):
        raise ValueError("invalid path")
    return Path(raw)


def _safe_identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _document_type(basename: str) -> FileType:
    suffix = Path(basename).suffix.casefold()
    if suffix in _SOURCE_SUFFIXES:
        return FileType.SOURCE_CODE
    if suffix in _TEXT_SUFFIXES:
        return FileType.TEXT
    if suffix == ".pdf":
        return FileType.PDF
    raise FileReferenceConflict()
