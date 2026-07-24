from __future__ import annotations

import stat
from os import stat_result
from pathlib import Path, PureWindowsPath

from embedded_copilot.input.exceptions import InputValidationError


def validate_input_root(root: str | Path) -> Path:
    try:
        path = Path(root)
        if path.is_symlink() or not path.is_dir():
            raise ValueError("invalid root")
        return path.resolve(strict=True)
    except Exception:
        raise InputValidationError("input root is invalid") from None


def validate_relative_file(
    root: Path,
    relative_path: str | Path,
) -> tuple[Path, stat_result]:
    try:
        if not isinstance(relative_path, (str, Path)):
            raise TypeError("invalid path")
        raw = str(relative_path)
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
            raise ValueError("invalid path")

        candidate = root
        for part in relative.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ValueError("symlink is forbidden")
            candidate.lstat()

        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("path escaped root")
        file_stat = candidate.stat(follow_symlinks=False)
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("path is not a regular file")
        return candidate, file_stat
    except Exception:
        raise InputValidationError("attachment metadata is invalid") from None
