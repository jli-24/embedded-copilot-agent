from __future__ import annotations

import os
import stat
from pathlib import Path

from embedded_copilot.engineering.models import (
    EngineeringSourceReference,
    ResolvedEngineeringSource,
)
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


MAX_DATASHEET_BYTES = 25 * 1024 * 1024
MAX_FIRMWARE_FILE_BYTES = 2 * 1024 * 1024
MAX_FIRMWARE_TOTAL_BYTES = 8 * 1024 * 1024
MAX_FIRMWARE_FILES = 8
_SOURCE_SUFFIXES = frozenset({".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"})
_C_SUFFIXES = frozenset({".c", ".h"})
_C_CONTENT_TYPES = frozenset({"text/x-c", "text/plain"})
_CPP_CONTENT_TYPES = frozenset({"text/x-c++", "text/plain"})


class EngineeringResolutionError(RuntimeError):
    """Safe error raised at the trusted-root boundary."""


class TrustedEngineeringResolver:
    """Read only explicitly declared engineering attachments from one root."""

    def __init__(self, root: str | Path) -> None:
        try:
            candidate = Path(root)
            if candidate.is_symlink() or not candidate.is_dir():
                raise ValueError("invalid root")
            self._root = candidate.resolve(strict=True)
        except Exception:
            raise EngineeringResolutionError(
                "Engineering input root is invalid"
            ) from None

    def resolve(
        self,
        context: UnifiedInputContext,
    ) -> tuple[ResolvedEngineeringSource, ...]:
        if not isinstance(context, UnifiedInputContext):
            raise EngineeringResolutionError("Engineering input context is invalid")
        if any(
            self._is_datasheet_candidate(attachment)
            and not self._is_datasheet(attachment)
            for attachment in context.attachments
        ):
            raise EngineeringResolutionError("Datasheet input is invalid")
        if any(
            self._is_firmware_candidate(attachment)
            and not self._is_firmware(attachment)
            for attachment in context.attachments
        ):
            raise EngineeringResolutionError("Firmware input is invalid")
        supported = tuple(
            attachment
            for attachment in context.attachments
            if self._is_datasheet(attachment) or self._is_firmware(attachment)
        )
        datasheets = [item for item in supported if self._is_datasheet(item)]
        firmware = [item for item in supported if self._is_firmware(item)]
        if len(datasheets) > 1:
            raise EngineeringResolutionError("Datasheet input is invalid")
        if len(firmware) > MAX_FIRMWARE_FILES:
            raise EngineeringResolutionError("Firmware input is invalid")
        names = [item.filename.casefold() for item in supported]
        if len(names) != len(set(names)):
            raise EngineeringResolutionError("Engineering input mapping is invalid")

        resolved: list[ResolvedEngineeringSource] = []
        firmware_total = 0
        for attachment in supported:
            limit = (
                MAX_DATASHEET_BYTES
                if self._is_datasheet(attachment)
                else MAX_FIRMWARE_FILE_BYTES
            )
            data = self._read_explicit(attachment, limit=limit)
            if self._is_firmware(attachment):
                firmware_total += len(data)
                if firmware_total > MAX_FIRMWARE_TOTAL_BYTES:
                    raise EngineeringResolutionError("Firmware input is invalid")
                try:
                    data.decode("utf-8-sig", errors="strict")
                except UnicodeDecodeError:
                    raise EngineeringResolutionError(
                        "Firmware input encoding is invalid"
                    ) from None
            resolved.append(
                ResolvedEngineeringSource(
                    reference=EngineeringSourceReference(
                        attachment_id=attachment.id,
                        source_id=f"attachment:{attachment.id}",
                        filename=attachment.filename,
                    ),
                    media_type=attachment.media_type,
                    content_type=attachment.content_type,
                    data=data,
                )
            )
        return tuple(resolved)

    def _read_explicit(self, attachment: UserAttachment, *, limit: int) -> bytes:
        try:
            candidate = self._root / attachment.filename
            if candidate.parent != self._root or candidate.is_symlink():
                raise ValueError("invalid target")
            before = candidate.lstat()
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_size != attachment.size_bytes
                or before.st_size <= 0
                or before.st_size > limit
            ):
                raise ValueError("invalid file")
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(candidate, flags)
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_size != before.st_size
                    or not _same_file(before, opened)
                ):
                    raise ValueError("source changed")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = os.read(descriptor, min(64 * 1024, limit + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("source too large")
                    chunks.append(chunk)
                if total != before.st_size:
                    raise ValueError("source changed")
                completed = os.fstat(descriptor)
                after = candidate.lstat()
                if (
                    _file_snapshot(completed) != _file_snapshot(opened)
                    or _file_snapshot(after) != _file_snapshot(before)
                ):
                    raise ValueError("source changed")
                return b"".join(chunks)
            finally:
                os.close(descriptor)
        except Exception:
            raise EngineeringResolutionError(
                "Engineering source validation failed"
            ) from None

    @staticmethod
    def _is_datasheet(attachment: UserAttachment) -> bool:
        return (
            TrustedEngineeringResolver._is_datasheet_candidate(attachment)
            and attachment.content_type == "application/pdf"
        )

    @staticmethod
    def _is_firmware(attachment: UserAttachment) -> bool:
        if not TrustedEngineeringResolver._is_firmware_candidate(attachment):
            return False
        suffix = Path(attachment.filename).suffix.casefold()
        allowed = _C_CONTENT_TYPES if suffix in _C_SUFFIXES else _CPP_CONTENT_TYPES
        return attachment.content_type in allowed

    @staticmethod
    def _is_datasheet_candidate(attachment: UserAttachment) -> bool:
        return (
            attachment.media_type is AttachmentType.DOCUMENT
            and Path(attachment.filename).suffix.casefold() == ".pdf"
        )

    @staticmethod
    def _is_firmware_candidate(attachment: UserAttachment) -> bool:
        return (
            attachment.media_type is AttachmentType.SOURCE_CODE
            and Path(attachment.filename).suffix.casefold() in _SOURCE_SUFFIXES
        )


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _file_snapshot(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_mode,
        value.st_size,
        value.st_dev,
        value.st_ino,
        value.st_mtime_ns,
    )
