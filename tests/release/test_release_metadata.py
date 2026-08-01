from __future__ import annotations

import tomllib
from pathlib import Path

from embedded_copilot import __version__
from embedded_copilot.core.config import Settings
from embedded_copilot.schemas.api import HealthResponse


def _headings(path: str) -> tuple[str, ...]:
    return tuple(
        line.removeprefix("## ").strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    )


def test_project_versions_are_synchronized_to_v045() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == "0.45.0"
    assert __version__ == "0.45.0"
    assert Settings().version == "0.45.0"
    assert HealthResponse(status="ok", mode="offline").version == "0.45.0"


def test_readme_has_release_structure_and_required_limitations() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    expected = (
        "Overview",
        "Architecture",
        "v0.45 Architecture",
        "v0.45 Highlights",
        "v0.44 Architecture",
        "v0.44 Highlights",
        "v0.43 Architecture",
        "v0.43 Highlights",
        "v0.42 Architecture",
        "v0.42 Highlights",
        "v0.41 Architecture",
        "v0.41 Highlights",
        "v0.40 Architecture",
        "v0.40 Highlights",
        "Features",
        "Demo",
        "Benchmark",
        "Installation",
        "Deployment",
        "Engineering Design",
        "Limitations",
    )

    assert _headings("README.md") == expected
    assert all(
        value in readme
        for value in (
            "Datasheet analysis",
            "PCB review",
            "Firmware analysis",
            "Debug diagnosis",
            "不自动修改 PCB",
            "不自动烧录",
            "不替代 EDA DRC",
            "不替代人工审核",
        )
    )


def test_v020_release_note_has_required_sections() -> None:
    release_path = Path("docs/release/v0.20.md")

    assert release_path.is_file()
    assert _headings(str(release_path)) == (
        "Version History",
        "Architecture",
        "Benchmark Results",
        "Known Limitations",
        "Future Roadmap",
    )
