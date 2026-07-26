from __future__ import annotations

import copy
import os
import stat

from embedded_copilot.file_intelligence.extractor import (
    FileExtractor,
    TemporaryFileSummary,
)
from embedded_copilot.file_intelligence.security import RootedReferenceResolver
from embedded_copilot.multimodal.context import AttachmentBinding
from embedded_copilot.multimodal.models import MultimodalInputType

DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class FileReadRejected(RuntimeError):
    """The referenced file cannot be read through the secure boundary."""


class SecureFileReader:
    def __init__(
        self,
        resolver: RootedReferenceResolver,
        *,
        max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> None:
        if (
            isinstance(max_size_bytes, bool)
            or not isinstance(max_size_bytes, int)
            or max_size_bytes < 1
        ):
            raise ValueError("file reader size limit is invalid")
        self._resolver = resolver
        self._max_size_bytes = max_size_bytes

    def extract(
        self,
        binding: AttachmentBinding,
        extractor: FileExtractor,
    ) -> TemporaryFileSummary:
        try:
            snapshot = AttachmentBinding.model_validate(
                copy.deepcopy(binding.model_dump(mode="python"))
            )
            if snapshot.input.type not in {
                MultimodalInputType.FILE,
                MultimodalInputType.IMAGE,
            }:
                raise ValueError("unsupported reference")
            root = self._resolver.root
            candidate = self._resolver.resolve(snapshot)
            if candidate.name != snapshot.basename or not candidate.is_relative_to(
                root
            ):
                raise ValueError("target mismatch")

            cursor = root
            for part in candidate.relative_to(root).parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError("symlink is forbidden")
                cursor.lstat()

            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError("target escaped root")
            file_stat = resolved.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or file_stat.st_size != snapshot.size_bytes
                or file_stat.st_size < 1
                or file_stat.st_size > self._max_size_bytes
            ):
                raise ValueError("file size is invalid")

            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(resolved, flags)
            try:
                opened_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened_stat.st_mode)
                    or opened_stat.st_size != file_stat.st_size
                ):
                    raise ValueError("file changed")
                with os.fdopen(descriptor, "rb", closefd=True) as stream:
                    descriptor = -1
                    raw_summary = extractor.extract(stream, binding=snapshot)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)

            summary = TemporaryFileSummary.model_validate(
                copy.deepcopy(raw_summary.model_dump(mode="python"))
            )
            if (
                summary.reference_id.casefold()
                != snapshot.input.reference_id.casefold()
            ):
                raise ValueError("summary reference mismatch")
            return summary
        except FileReadRejected:
            raise
        except Exception:
            raise FileReadRejected("file reference validation failed") from None
