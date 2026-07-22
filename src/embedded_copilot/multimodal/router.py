from __future__ import annotations

from pathlib import Path

from embedded_copilot.multimodal.models import FileType


class FileRouter:
    _EXTENSION_TYPES = {
        ".pdf": FileType.PDF,
        ".png": FileType.IMAGE,
        ".jpg": FileType.IMAGE,
        ".jpeg": FileType.IMAGE,
        ".webp": FileType.IMAGE,
        ".c": FileType.CODE,
        ".h": FileType.CODE,
        ".cpp": FileType.CODE,
        ".py": FileType.CODE,
        ".rs": FileType.CODE,
        ".md": FileType.TEXT,
        ".txt": FileType.TEXT,
    }

    @classmethod
    def route(cls, file_path: str | Path) -> FileType:
        suffix = Path(file_path).suffix.lower()
        return cls._EXTENSION_TYPES.get(suffix, FileType.UNKNOWN)
