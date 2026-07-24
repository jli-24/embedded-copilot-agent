from __future__ import annotations

import pytest

from embedded_copilot.input.classifier import AttachmentClassifier
from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.models import AttachmentType


@pytest.mark.parametrize(
    ("filename", "expected_type", "expected_content_type"),
    [
        ("board.png", AttachmentType.IMAGE, "image/png"),
        ("board.jpg", AttachmentType.IMAGE, "image/jpeg"),
        ("board.jpeg", AttachmentType.IMAGE, "image/jpeg"),
        ("main.c", AttachmentType.SOURCE_CODE, "text/x-c"),
        ("main.cpp", AttachmentType.SOURCE_CODE, "text/x-c++"),
        ("main.h", AttachmentType.SOURCE_CODE, "text/x-c"),
        ("main.hpp", AttachmentType.SOURCE_CODE, "text/x-c++"),
        ("tool.py", AttachmentType.SOURCE_CODE, "text/x-python"),
        ("serial.log", AttachmentType.LOG, "text/plain"),
        ("serial.txt", AttachmentType.LOG, "text/plain"),
        ("board.kicad_pcb", AttachmentType.EDA, "application/x-kicad-pcb"),
        ("board.kicad_sch", AttachmentType.EDA, "application/x-kicad-schematic"),
        ("board.brd", AttachmentType.EDA, "application/x-eda-board"),
        ("manual.pdf", AttachmentType.DOCUMENT, "application/pdf"),
        (
            "manual.docx",
            AttachmentType.DOCUMENT,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("notes.md", AttachmentType.DOCUMENT, "text/markdown"),
    ],
)
def test_classifier_maps_supported_extensions_deterministically(
    filename: str,
    expected_type: AttachmentType,
    expected_content_type: str,
) -> None:
    assert AttachmentClassifier.classify(filename) is expected_type
    assert (
        AttachmentClassifier.canonical_content_type(filename)
        == expected_content_type
    )


def test_classifier_normalizes_case_and_content_type_parameters() -> None:
    assert (
        AttachmentClassifier.classify("BOARD.PNG", " Image/PNG; charset=binary ")
        is AttachmentType.IMAGE
    )
    assert AttachmentClassifier.canonical_content_type("BOARD.PNG") == "image/png"


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("archive.zip", None),
        ("board.png.exe", "image/png"),
        ("board", "image/png"),
        ("../board.png", "image/png"),
        ("board.png", "application/pdf"),
        ("manual.pdf", "application/octet-stream"),
    ],
)
def test_classifier_rejects_unknown_or_inconsistent_types(
    filename: str,
    content_type: str | None,
) -> None:
    with pytest.raises(InputValidationError, match="attachment type is invalid"):
        AttachmentClassifier.classify(filename, content_type)


def test_classifier_allows_common_plain_text_mime_for_source_and_eda() -> None:
    assert (
        AttachmentClassifier.classify("main.c", "text/plain")
        is AttachmentType.SOURCE_CODE
    )
    assert (
        AttachmentClassifier.classify("board.kicad_sch", "text/plain")
        is AttachmentType.EDA
    )
