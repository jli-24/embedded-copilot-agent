from __future__ import annotations

from pathlib import Path

import pytest

from embedded_copilot.datasheet.exceptions import DatasheetParseError
from embedded_copilot.datasheet.parser import (
    MarkdownDatasheetParser,
    RootedDatasheetSourceResolver,
)
from embedded_copilot.input import InputLoader

from tests.datasheet.parser.fixtures import ESP32_MARKDOWN


def _parser(root: Path, filename: str = "esp32-s3.md") -> MarkdownDatasheetParser:
    return MarkdownDatasheetParser(
        RootedDatasheetSourceResolver(root, {"datasheet-1": filename})
    )


def _attachment(root: Path, filename: str = "esp32-s3.md"):
    return InputLoader(root).load(filename, attachment_id="datasheet-1")


def test_markdown_parser_extracts_deterministic_structured_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "esp32-s3.md"
    path.write_text(ESP32_MARKDOWN, encoding="utf-8")
    parser = _parser(tmp_path)
    attachment = _attachment(tmp_path)

    first = parser.parse(attachment)
    second = parser.parse(attachment)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.component.part_number == "ESP32-S3"
    assert first.component.package == "QFN-56"
    assert [pin.number for pin in first.pins] == ["43", "44"]
    assert first.interfaces[0].protocol == "UART"
    assert first.interfaces[0].pins == ("43", "44")
    assert [spec.unit for spec in first.electrical_specs] == ["V", "A"]
    assert first.electrical_specs[1].typical_value == pytest.approx(0.025)
    assert first.power_requirements == first.electrical_specs
    assert first.metadata == {
        "format": "markdown",
        "record_count": 5,
    }


@pytest.mark.parametrize(
    "content",
    [
        " \n",
        "Manufacturer: Espressif\nPart Number: ESP32-S3",
        ESP32_MARKDOWN.replace("Package: QFN-56", "Package: SOIC-8"),
        ESP32_MARKDOWN.replace("| UART0 | UART |", "| UART0 | LIN |"),
        ESP32_MARKDOWN.replace("| 44 | U0RXD", "| 43 | U0RXD"),
        ESP32_MARKDOWN.replace("| 3.0 | 3.3 | 3.6 |", "| 3.6 | 3.3 | 3.0 |"),
    ],
)
def test_markdown_parser_safely_rejects_incomplete_or_malformed_documents(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "private-datasheet.md"
    path.write_text(content, encoding="utf-8")
    attachment = _attachment(tmp_path, path.name)

    with pytest.raises(DatasheetParseError) as captured:
        _parser(tmp_path, path.name).parse(attachment)

    message = str(captured.value)
    assert str(tmp_path) not in message
    assert "Espressif" not in message
    assert "private-datasheet.md" not in message


def test_markdown_parser_reads_only_explicit_attachment_and_creates_no_files(
    tmp_path: Path,
) -> None:
    target = tmp_path / "esp32-s3.md"
    target.write_text(ESP32_MARKDOWN, encoding="utf-8")
    (tmp_path / "unmapped-secret.md").write_text(
        "PRIVATE_DOCUMENT_SENTINEL",
        encoding="utf-8",
    )
    before = sorted(path.name for path in tmp_path.iterdir())

    model = _parser(tmp_path).parse(_attachment(tmp_path))

    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert "PRIVATE_DOCUMENT_SENTINEL" not in model.model_dump_json()


def test_markdown_parser_rejects_oversize_and_changed_sources(tmp_path: Path) -> None:
    path = tmp_path / "esp32-s3.md"
    path.write_text(ESP32_MARKDOWN, encoding="utf-8")
    attachment = _attachment(tmp_path)

    parser = MarkdownDatasheetParser(
        RootedDatasheetSourceResolver(tmp_path, {"datasheet-1": path.name}),
        max_size_bytes=16,
    )
    with pytest.raises(DatasheetParseError):
        parser.parse(attachment)

    path.write_text(f"{ESP32_MARKDOWN}\nchanged", encoding="utf-8")
    with pytest.raises(DatasheetParseError):
        _parser(tmp_path).parse(attachment)


@pytest.mark.parametrize(
    "mapping",
    [
        {"datasheet-1": "../outside.md"},
        {"datasheet-1": "C:/private/outside.md"},
        {"datasheet-1": "missing/../outside.md"},
    ],
)
def test_source_resolver_rejects_untrusted_mappings(
    tmp_path: Path,
    mapping: dict[str, str],
) -> None:
    with pytest.raises(DatasheetParseError):
        RootedDatasheetSourceResolver(tmp_path, mapping)
