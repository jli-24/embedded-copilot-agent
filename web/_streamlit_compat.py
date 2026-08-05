"""Compatibility helpers for Streamlit's relative AppTest paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any


_PATCH_MARKER = "_embedded_copilot_path_compat"


def install_app_test_path_compat() -> None:
    """Resolve relative AppTest paths from the repository as a stable fallback.

    Streamlit versions that cannot find a relative path from the current
    working directory fall back to the caller's directory.  That turns the
    test path ``web/app.py`` into ``tests/web/web/app.py`` when pytest is
    launched outside the repository root.  The patch only applies when the
    repository candidate exists and leaves normal and CLI execution unchanged.
    """

    try:
        from streamlit.testing.v1 import AppTest
    except Exception:
        return
    if getattr(AppTest, _PATCH_MARKER, False):
        return

    original = AppTest.from_file
    repository_root = Path(__file__).resolve().parents[1]

    @classmethod
    def from_file(
        cls: type[Any], script_path: str | Path, *, default_timeout: float = 3
    ) -> Any:
        candidate = Path(script_path)
        if not candidate.is_absolute():
            repository_candidate = repository_root / candidate
            if repository_candidate.is_file():
                script_path = repository_candidate.resolve()
        return original.__func__(
            cls,
            script_path,
            default_timeout=default_timeout,
        )

    AppTest.from_file = from_file
    setattr(AppTest, _PATCH_MARKER, True)


__all__ = ["install_app_test_path_compat"]
