from __future__ import annotations

import os
import stat

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    Extractor,
    FileReferenceRequest,
)
from embedded_copilot.file_runtime.exceptions import (
    FileReferenceConflict,
    FileReferenceNotFound,
    FileRuntimeError,
    FileRuntimeUnavailable,
)
from embedded_copilot.file_runtime.reader.resolver import RootedFileResolver

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class SecureFileReader:
    __slots__ = ("_max_size_bytes", "_resolver")

    def __init__(
        self,
        resolver: RootedFileResolver,
        *,
        max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> None:
        if (
            isinstance(max_size_bytes, bool)
            or not isinstance(max_size_bytes, int)
            or max_size_bytes < 1
        ):
            raise FileRuntimeUnavailable()
        self._resolver = resolver
        self._max_size_bytes = max_size_bytes

    def extract(
        self,
        request: FileReferenceRequest,
        extractor: Extractor,
    ) -> DocumentSummary:
        resolved = self._resolver.resolve(request)
        reference = resolved.reference
        path = resolved.path
        try:
            before = path.lstat()
        except FileNotFoundError:
            raise FileReferenceNotFound() from None
        except Exception:
            raise FileReferenceConflict() from None
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size != reference.size_bytes
            or before.st_size < 1
            or before.st_size > self._max_size_bytes
        ):
            raise FileReferenceConflict()

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
        except FileNotFoundError:
            raise FileReferenceNotFound() from None
        except Exception:
            raise FileReferenceConflict() from None
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or _file_snapshot(opened) != _file_snapshot(before)
            ):
                raise FileReferenceConflict()
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                try:
                    raw_summary = extractor.extract(stream, reference=reference)
                except FileRuntimeError:
                    raise
                except Exception:
                    raise FileRuntimeUnavailable() from None
                completed = os.fstat(stream.fileno())
                try:
                    after = path.lstat()
                except Exception:
                    raise FileReferenceConflict() from None
                if (
                    _file_snapshot(completed) != _file_snapshot(opened)
                    or _file_snapshot(after) != _file_snapshot(before)
                ):
                    raise FileReferenceConflict()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        if not isinstance(raw_summary, DocumentSummary):
            raise FileRuntimeUnavailable()
        summary = raw_summary.model_copy(deep=True)
        if (
            summary.file_id.casefold() != reference.file_id.casefold()
            or summary.document_type is not reference.document_type
        ):
            raise FileReferenceConflict()
        return summary


def _file_snapshot(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_mode,
        value.st_size,
        value.st_dev,
        value.st_ino,
        value.st_mtime_ns,
    )
