from __future__ import annotations

import logging
from pathlib import Path

import fitz
import pytest
from PIL import Image

from embedded_copilot.multimodal.models import FileType
from embedded_copilot.multimodal.processor import MultimodalProcessor


_STANDARD_LOG_FIELDS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message"}


def _write_trace_fixture(path: Path, secret: str) -> None:
    if path.suffix == ".txt":
        path.write_text(secret, encoding="utf-8")
    elif path.suffix == ".pdf":
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text((72, 72), secret)
        pdf.save(path)
        pdf.close()
    else:
        Image.new("RGB", (4, 3), color="red").save(path)


@pytest.mark.parametrize(
    ("filename", "expected_type", "secret"),
    [
        ("notes.txt", FileType.TEXT, "TEXT_BODY_SENTINEL"),
        ("manual.pdf", FileType.PDF, "PDF_TEXT_SENTINEL"),
        ("board.png", FileType.IMAGE, "IMAGE_BINARY_SENTINEL"),
    ],
)
def test_processor_logs_trace_without_file_contents(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    filename: str,
    expected_type: FileType,
    secret: str,
) -> None:
    path = tmp_path / filename
    _write_trace_fixture(path, secret)
    forbidden_payload = path.read_bytes().hex() if path.suffix == ".png" else secret
    caplog.set_level(logging.INFO, logger="embedded_copilot.multimodal")

    MultimodalProcessor.process(path, trace_id="abc123")

    records = [
        record
        for record in caplog.records
        if record.name == "embedded_copilot.multimodal"
    ]
    assert [getattr(record, "event_name", None) for record in records] == [
        "multimodal_processing_started",
        "multimodal_processing_completed",
    ]
    assert all(getattr(record, "trace_id", None) == "abc123" for record in records)
    assert all(
        getattr(record, "file_type", None) == expected_type.value
        for record in records
    )

    absolute_path = str(path.resolve())
    for record in records:
        custom_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_FIELDS
        }
        assert set(custom_fields) <= {
            "event_name",
            "trace_id",
            "file_type",
            "outcome",
        }
        assert not any(
            isinstance(value, (bytes, bytearray))
            for value in custom_fields.values()
        )
        rendered = f"{record.getMessage()} {custom_fields!r}"
        assert absolute_path not in rendered
        assert forbidden_payload not in rendered
