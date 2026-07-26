from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import BinaryIO, TypeVar

from pydantic import BaseModel

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    Extractor,
    FileReferenceRequest,
    ReadOnlyExtractor,
)
from embedded_copilot.file_runtime.exceptions import (
    FileReferenceConflict,
    FileRuntimeError,
    FileRuntimeUnavailable,
)
from embedded_copilot.file_runtime.reader.resolver import (
    FileSnapshot,
    RootedFileResolver,
    _file_snapshot,
    _stable_file_identity,
)

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
ExtractionResultT = TypeVar("ExtractionResultT", bound=BaseModel)


class _BoundedReadStream:
    __slots__ = ("_raw", "_remaining")

    def __init__(self, raw: BinaryIO, *, size_bytes: int) -> None:
        self._raw = raw
        self._remaining = size_bytes

    @property
    def closed(self) -> bool:
        return self._raw.closed

    def fileno(self) -> int:
        return self._raw.fileno()

    def read(self, size: int = -1) -> bytes:
        if self._remaining == 0:
            if self._raw.read(1):
                raise FileReferenceConflict()
            return b""
        limit = self._remaining if size < 0 else min(size, self._remaining)
        chunk = self._raw.read(limit)
        if not isinstance(chunk, bytes) or not chunk:
            raise FileReferenceConflict()
        self._remaining -= len(chunk)
        return chunk

    def verify_consumed(self) -> None:
        if self._remaining != 0:
            raise FileReferenceConflict()
        self.read(1)


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
        return self.extract_model(
            request,
            extractor,
            result_type=DocumentSummary,
        )

    def extract_model(
        self,
        request: FileReferenceRequest,
        extractor: ReadOnlyExtractor[ExtractionResultT],
        *,
        result_type: type[ExtractionResultT],
    ) -> ExtractionResultT:
        if (
            not isinstance(result_type, type)
            or not issubclass(result_type, BaseModel)
            or result_type.model_config.get("frozen") is not True
            or result_type.model_config.get("extra") != "forbid"
        ):
            raise FileRuntimeUnavailable()
        resolved = self._resolver.resolve(request)
        reference = resolved.reference
        path = resolved.path
        descriptor = resolved.descriptor
        try:
            _validate_path_snapshots(
                resolved.snapshots,
                allowed_leaf_ctimes=resolved.leaf_ctimes,
            )
            opened = os.fstat(descriptor)
            expected = resolved.snapshots[-1][1]
            if (
                not stat.S_ISREG(opened.st_mode)
                or _file_snapshot(opened) != expected
                or opened.st_size != reference.size_bytes
                or opened.st_size < 1
                or opened.st_size > self._max_size_bytes
            ):
                raise FileReferenceConflict()
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                bounded_stream = _BoundedReadStream(
                    stream,
                    size_bytes=reference.size_bytes,
                )
                try:
                    raw_result = extractor.extract(
                        bounded_stream,
                        reference=reference,
                    )
                    bounded_stream.verify_consumed()
                except FileRuntimeError:
                    raise
                except Exception:
                    raise FileRuntimeUnavailable() from None
                completed = os.fstat(stream.fileno())
                try:
                    after = path.lstat()
                except Exception:
                    raise FileReferenceConflict() from None
                after_snapshot = _file_snapshot(after)
                if (
                    _file_snapshot(completed) != _file_snapshot(opened)
                    or _stable_file_identity(after_snapshot)
                    != _stable_file_identity(expected)
                    or after_snapshot[-1] not in resolved.leaf_ctimes
                ):
                    raise FileReferenceConflict()
            _validate_path_snapshots(
                resolved.snapshots,
                allowed_leaf_ctimes=resolved.leaf_ctimes,
            )
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        if type(raw_result) is not result_type:
            raise FileRuntimeUnavailable()
        result = raw_result.model_copy(deep=True)
        result_file_id = getattr(result, "file_id", None)
        if (
            result_file_id is not None
            and (
                not isinstance(result_file_id, str)
                or result_file_id.casefold() != reference.file_id.casefold()
            )
        ):
            raise FileReferenceConflict()
        result_document_type = getattr(result, "document_type", None)
        if (
            result_document_type is not None
            and result_document_type is not reference.document_type
        ):
            raise FileReferenceConflict()
        return result


def _validate_path_snapshots(
    snapshots: tuple[tuple[Path, FileSnapshot], ...],
    *,
    allowed_leaf_ctimes: frozenset[int] | None = None,
) -> None:
    try:
        last_index = len(snapshots) - 1
        for index, (path, expected) in enumerate(snapshots):
            actual = _file_snapshot(path.lstat())
            if actual == expected:
                continue
            if (
                allowed_leaf_ctimes is not None
                and index == last_index
                and _stable_file_identity(actual)
                == _stable_file_identity(expected)
                and actual[-1] in allowed_leaf_ctimes
            ):
                continue
            if actual != expected:
                raise FileReferenceConflict()
    except FileRuntimeError:
        raise
    except Exception:
        raise FileReferenceConflict() from None
