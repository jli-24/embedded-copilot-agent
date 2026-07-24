from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import Protocol, runtime_checkable

from embedded_copilot.input.models import UserAttachment
from embedded_copilot.pcb.exceptions import PCBParseError
from embedded_copilot.pcb.models import UnifiedPCBModel


@runtime_checkable
class PCBSourceResolver(Protocol):
    @property
    def root(self) -> Path: ...

    def resolve(self, attachment: UserAttachment) -> Path: ...


@runtime_checkable
class PCBParser(Protocol):
    def parse(self, attachment: UserAttachment) -> UnifiedPCBModel: ...


class RootedPCBSourceResolver:
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
            raise PCBParseError("PCB source resolver is invalid") from None

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
            raise PCBParseError("PCB source resolution failed") from None
