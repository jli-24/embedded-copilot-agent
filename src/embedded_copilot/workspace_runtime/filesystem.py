from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_WORKSPACE_FILE_SIZE = 1024 * 1024


class WorkspaceFileInvalid(ValueError):
    pass


@dataclass(frozen=True)
class FileIdentity:
    mode: int
    size: int
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "FileIdentity":
        return cls(
            mode=value.st_mode,
            size=value.st_size,
            device=value.st_dev,
            inode=value.st_ino,
            mtime_ns=value.st_mtime_ns,
            ctime_ns=value.st_ctime_ns,
        )

    def stable_key(self) -> tuple[int, int, int, int, int]:
        """Return identity fields stable across descriptor and path stat calls."""
        return (self.mode, self.size, self.device, self.inode, self.mtime_ns)


@dataclass(frozen=True)
class DirectoryIdentity:
    mode: int
    device: int
    inode: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "DirectoryIdentity":
        return cls(
            mode=value.st_mode,
            device=value.st_dev,
            inode=value.st_ino,
        )


@dataclass(frozen=True)
class ValidatedWorkspaceFile:
    path: Path
    content: bytes
    identity: FileIdentity
    parent_identities: tuple[DirectoryIdentity, ...]


def read_workspace_file(root: Path, relative_path: str) -> ValidatedWorkspaceFile:
    path = root.joinpath(*relative_path.split("/"))
    expected_parents = _assert_bound_path(root, path)
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            _assert_regular_file(before)
            _assert_bound_identity(root, path, before, expected_parents)
            content = handle.read(MAX_WORKSPACE_FILE_SIZE + 1)
            after = os.fstat(handle.fileno())
            _assert_regular_file(after)
            if (
                FileIdentity.from_stat(before).stable_key()
                != FileIdentity.from_stat(after).stable_key()
            ):
                raise WorkspaceFileInvalid("workspace file changed while reading")
            current_parents = _assert_bound_identity(
                root, path, after, expected_parents
            )
    except (OSError, ValueError) as exc:
        if isinstance(exc, WorkspaceFileInvalid):
            raise
        raise WorkspaceFileInvalid("workspace file is unavailable") from None
    if len(content) > MAX_WORKSPACE_FILE_SIZE or len(content) != after.st_size:
        raise WorkspaceFileInvalid("workspace file size is invalid")
    if b"\x00" in content:
        raise WorkspaceFileInvalid("workspace file is not text")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        raise WorkspaceFileInvalid("workspace file is not UTF-8") from None
    return ValidatedWorkspaceFile(
        path=path,
        content=content,
        identity=FileIdentity.from_stat(after),
        parent_identities=current_parents,
    )


def assert_workspace_file_identity(
    root: Path,
    relative_path: str,
    expected: FileIdentity,
    expected_parents: tuple[DirectoryIdentity, ...],
) -> None:
    path = root.joinpath(*relative_path.split("/"))
    _assert_bound_path(root, path)
    try:
        current = path.stat(follow_symlinks=False)
    except OSError:
        raise WorkspaceFileInvalid("workspace file is unavailable") from None
    _assert_regular_file(current)
    if FileIdentity.from_stat(current).stable_key() != expected.stable_key():
        raise WorkspaceFileInvalid("workspace file changed")
    _assert_bound_identity(root, path, current, expected_parents)


def _assert_bound_path(root: Path, path: Path) -> tuple[DirectoryIdentity, ...]:
    current = root
    parents: list[DirectoryIdentity] = []
    try:
        root_stat = root.lstat()
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise WorkspaceFileInvalid("workspace root is invalid")
        parents.append(DirectoryIdentity.from_stat(root_stat))
        parts = path.relative_to(root).parts
        for part in parts[:-1]:
            current = current / part
            current_stat = current.lstat()
            if stat.S_ISLNK(current_stat.st_mode) or not stat.S_ISDIR(
                current_stat.st_mode
            ):
                raise WorkspaceFileInvalid("workspace symlink is forbidden")
            parents.append(DirectoryIdentity.from_stat(current_stat))
        leaf_stat = path.lstat()
        if stat.S_ISLNK(leaf_stat.st_mode):
            raise WorkspaceFileInvalid("workspace symlink is forbidden")
        resolved = path.resolve(strict=True)
    except (OSError, ValueError):
        raise WorkspaceFileInvalid("workspace path is unavailable") from None
    if not resolved.is_relative_to(root):
        raise WorkspaceFileInvalid("workspace path escapes trusted root")
    return tuple(parents)


def _assert_bound_identity(
    root: Path,
    path: Path,
    expected: os.stat_result,
    expected_parents: tuple[DirectoryIdentity, ...],
) -> tuple[DirectoryIdentity, ...]:
    current_parents = _assert_bound_path(root, path)
    if current_parents != expected_parents:
        raise WorkspaceFileInvalid("workspace parent identity changed")
    try:
        current = path.stat(follow_symlinks=False)
    except OSError:
        raise WorkspaceFileInvalid("workspace file is unavailable") from None
    if (
        FileIdentity.from_stat(current).stable_key()
        != FileIdentity.from_stat(expected).stable_key()
    ):
        raise WorkspaceFileInvalid("workspace path identity changed")
    return current_parents


def _assert_regular_file(value: os.stat_result) -> None:
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_size < 0
        or value.st_size > MAX_WORKSPACE_FILE_SIZE
    ):
        raise WorkspaceFileInvalid("workspace file is invalid")
