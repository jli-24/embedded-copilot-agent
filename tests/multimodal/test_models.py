from __future__ import annotations

from typing import get_type_hints

import pytest
from pydantic import ValidationError

from embedded_copilot.multimodal.models import FileDocument, FileType


def test_file_type_declares_phase_one_values() -> None:
    assert set(FileType) == {
        FileType.PDF,
        FileType.IMAGE,
        FileType.CODE,
        FileType.TEXT,
        FileType.UNKNOWN,
    }
    assert [file_type.value for file_type in FileType] == [
        "pdf",
        "image",
        "code",
        "text",
        "unknown",
    ]


def test_file_document_preserves_processor_metadata() -> None:
    metadata: dict[str, object] = {"page_count": 1, "pages": []}

    document = FileDocument(
        filename="manual.pdf",
        file_type=FileType.PDF,
        path="knowledge/manual.pdf",
        metadata=metadata,
    )

    assert document.metadata == metadata
    assert get_type_hints(FileDocument)["metadata"] == dict[str, object]


def test_file_document_rejects_blank_identifiers() -> None:
    with pytest.raises(ValidationError):
        FileDocument(
            filename="",
            file_type=FileType.TEXT,
            path="",
            metadata={},
        )


def test_file_document_is_frozen_and_forbids_extra_fields() -> None:
    document = FileDocument(
        filename="notes.txt",
        file_type=FileType.TEXT,
        path="notes.txt",
        metadata={"content": "notes"},
    )

    with pytest.raises(ValidationError):
        document.filename = "other.txt"

    with pytest.raises(ValidationError):
        FileDocument(
            filename="notes.txt",
            file_type=FileType.TEXT,
            path="notes.txt",
            metadata={},
            content="not a declared field",
        )
