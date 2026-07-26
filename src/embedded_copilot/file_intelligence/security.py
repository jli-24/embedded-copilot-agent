from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath

from embedded_copilot.intelligence._validation import safe_identifier
from embedded_copilot.multimodal.context import AttachmentBinding


class RootedReferenceResolver:
    """Resolve explicit reference ids under one trusted server-side root."""

    def __init__(
        self,
        root: str | Path,
        reference_paths: Mapping[str, str | Path],
    ) -> None:
        try:
            root_path = Path(root)
            if root_path.is_symlink() or not root_path.is_dir():
                raise ValueError("invalid root")
            self._root = root_path.resolve(strict=True)
            copied = copy.deepcopy(dict(reference_paths))
            self._paths: dict[str, Path] = {}
            for raw_id, raw_path in copied.items():
                reference_id = safe_identifier(raw_id, field="reference_id")
                if not isinstance(raw_path, (str, Path)):
                    raise ValueError("invalid path")
                raw = str(raw_path)
                relative = Path(raw)
                windows = PureWindowsPath(raw)
                if (
                    not raw.strip()
                    or relative.is_absolute()
                    or windows.is_absolute()
                    or relative.drive
                    or windows.drive
                    or raw.startswith(("/", "\\"))
                    or any(part in {"", ".", ".."} for part in relative.parts)
                ):
                    raise ValueError("invalid path")
                key = reference_id.casefold()
                if key in self._paths:
                    raise ValueError("duplicate reference")
                self._paths[key] = relative
        except Exception:
            raise ValueError("file reference resolver is invalid") from None

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, binding: AttachmentBinding) -> Path:
        try:
            relative = self._paths[binding.input.reference_id.casefold()]
        except (AttributeError, KeyError):
            raise ValueError("file reference resolution failed") from None
        return self._root / relative
