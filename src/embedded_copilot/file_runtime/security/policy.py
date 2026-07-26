from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from embedded_copilot.file_runtime.exceptions import FileRuntimeUnavailable

MAX_CONFIGURED_FILE_SIZE_BYTES = 100 * 1024 * 1024


class FileSettingsSource(Protocol):
    file_workspace_root: Path | None
    file_max_size_bytes: int


@dataclass(frozen=True, slots=True)
class FileSecurityPolicy:
    workspace_root: Path | None
    max_size_bytes: int


def load_file_security_policy(
    settings: FileSettingsSource,
) -> FileSecurityPolicy:
    root = settings.file_workspace_root
    limit = settings.file_max_size_bytes
    if (
        root is not None
        and not isinstance(root, Path)
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or limit > MAX_CONFIGURED_FILE_SIZE_BYTES
    ):
        raise FileRuntimeUnavailable()
    return FileSecurityPolicy(
        workspace_root=root,
        max_size_bytes=limit,
    )
