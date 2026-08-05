from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import web  # noqa: F401 - installs the compatibility layer


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("working_directory", (REPOSITORY_ROOT, REPOSITORY_ROOT.parent))
def test_relative_app_test_path_resolves_from_repository(
    monkeypatch: pytest.MonkeyPatch, working_directory: Path
) -> None:
    monkeypatch.chdir(working_directory)

    app = AppTest.from_file("web/app.py")

    assert Path(app._script_path).resolve() == (REPOSITORY_ROOT / "web" / "app.py").resolve()
