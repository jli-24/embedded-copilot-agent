from __future__ import annotations

from pathlib import Path

import pytest

from embedded_copilot.multimodal.models import FileType
from embedded_copilot.multimodal.router import FileRouter


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("manual.pdf", FileType.PDF),
        ("board.PNG", FileType.IMAGE),
        ("photo.jpg", FileType.IMAGE),
        ("photo.JPEG", FileType.IMAGE),
        ("diagram.webp", FileType.IMAGE),
        ("main.c", FileType.CODE),
        ("driver.h", FileType.CODE),
        ("task.cpp", FileType.CODE),
        ("script.py", FileType.CODE),
        ("module.rs", FileType.CODE),
        ("README.md", FileType.TEXT),
        ("notes.txt", FileType.TEXT),
    ],
)
def test_router_recognizes_supported_extensions(
    filename: str,
    expected: FileType,
) -> None:
    assert FileRouter.route(Path(filename)) is expected


@pytest.mark.parametrize("filename", ["archive.zip", "Makefile", "file."])
def test_router_returns_unknown_without_accessing_the_file(filename: str) -> None:
    assert FileRouter.route(filename) is FileType.UNKNOWN
