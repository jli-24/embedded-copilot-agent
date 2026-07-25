from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


_INPUT_ROOT_ENV = "EMBEDDED_COPILOT_ENGINEERING_INPUT_ROOT"


@dataclass(frozen=True, slots=True)
class EngineeringExtensionSettings:
    input_root: Path | None = None

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "EngineeringExtensionSettings":
        values = os.environ if environ is None else environ
        raw = values.get(_INPUT_ROOT_ENV)
        if raw is None or not raw.strip():
            return cls()
        return cls(input_root=Path(raw.strip()))


def real_pdf_backend_available() -> bool:
    """Probe the optional extension backend without importing it."""
    try:
        return importlib.util.find_spec("fitz") is not None
    except (ImportError, AttributeError, ValueError):
        return False
