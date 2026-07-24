from __future__ import annotations

import copy
import os
import stat
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import Protocol, runtime_checkable

from embedded_copilot.datasheet.exceptions import DatasheetParseError
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.input.models import AttachmentType, UserAttachment


DEFAULT_MAX_DATASHEET_SIZE_BYTES = 25 * 1024 * 1024


@runtime_checkable
class DatasheetSourceResolver(Protocol):
    @property
    def root(self) -> Path: ...

    def resolve(self, attachment: UserAttachment) -> Path: ...


@runtime_checkable
class DatasheetParser(Protocol):
    def parse(self, attachment: UserAttachment) -> UnifiedDatasheetModel: ...


class RootedDatasheetSourceResolver:
    """Resolve explicit attachment ids without inspecting directory contents."""

    def __init__(
        self,
        root: str | Path,
        attachment_paths: Mapping[str, str | Path],
    ) -> None:
        try:
            candidate_root = Path(root)
            if candidate_root.is_symlink() or not candidate_root.is_dir():
                raise ValueError("invalid root")
            self._root = candidate_root.resolve(strict=True)
            copied = copy.deepcopy(dict(attachment_paths))
            self._paths: dict[str, Path] = {}
            for raw_id, raw_path in copied.items():
                if not isinstance(raw_id, str) or not raw_id.strip():
                    raise ValueError("invalid attachment id")
                if not isinstance(raw_path, (str, Path)):
                    raise TypeError("invalid attachment path")
                raw = str(raw_path)
                relative = Path(raw)
                windows_path = PureWindowsPath(raw)
                if (
                    not raw.strip()
                    or relative.is_absolute()
                    or windows_path.is_absolute()
                    or relative.drive
                    or windows_path.drive
                    or not relative.parts
                    or any(part in {"", ".", ".."} for part in relative.parts)
                ):
                    raise ValueError("invalid attachment path")
                key = raw_id.strip().casefold()
                if key in self._paths:
                    raise ValueError("duplicate attachment id")
                self._paths[key] = relative
        except Exception:
            raise DatasheetParseError("Datasheet source resolver is invalid") from None

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, attachment: UserAttachment) -> Path:
        try:
            if not isinstance(attachment, UserAttachment):
                raise TypeError("invalid attachment")
            relative = self._paths[attachment.id.casefold()]
            return self._root.joinpath(relative)
        except Exception:
            raise DatasheetParseError("Datasheet source resolution failed") from None


def validate_parser_limit(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DatasheetParseError(f"Datasheet parser {label} limit is invalid")
    return value


def read_datasheet_source(
    attachment: UserAttachment,
    resolver: DatasheetSourceResolver,
    *,
    suffix: str,
    content_type: str,
    metadata_format: str,
    max_size_bytes: int,
) -> bytes:
    if (
        not isinstance(attachment, UserAttachment)
        or attachment.media_type is not AttachmentType.DOCUMENT
        or Path(attachment.filename).suffix.casefold() != suffix
        or attachment.content_type != content_type
        or attachment.metadata.get("format") != metadata_format
    ):
        raise DatasheetParseError("Datasheet attachment is unsupported")
    try:
        root = Path(resolver.root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("invalid root")
        trusted_root = root.resolve(strict=True)
        candidate = Path(resolver.resolve(attachment))
        if not candidate.is_absolute() or candidate.name != attachment.filename:
            raise ValueError("invalid target")
        if not candidate.is_relative_to(trusted_root):
            raise ValueError("target escaped root")

        cursor = trusted_root
        for part in candidate.relative_to(trusted_root).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("symlink is forbidden")
            cursor.lstat()

        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(trusted_root):
            raise ValueError("target escaped root")
        file_stat = resolved.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_size != attachment.size_bytes
            or file_stat.st_size <= 0
            or file_stat.st_size > max_size_bytes
        ):
            raise ValueError("invalid source size")

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
                raise ValueError("source changed")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(64 * 1024, max_size_bytes + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size_bytes:
                    raise ValueError("source is too large")
                chunks.append(chunk)
            if total != file_stat.st_size:
                raise ValueError("source changed")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except DatasheetParseError:
        raise
    except Exception:
        raise DatasheetParseError("Datasheet source validation failed") from None
