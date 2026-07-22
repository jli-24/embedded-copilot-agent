from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from embedded_copilot.knowledge.metadata import (
    MetadataError,
    load_document_metadata,
    metadata_sidecar_path,
)
from embedded_copilot.knowledge.models import DocumentMetadata


def test_document_metadata_strips_supported_fields() -> None:
    metadata = DocumentMetadata(
        chip="  ESP32-S3  ",
        manufacturer="  Espressif  ",
        category="  MCU  ",
        chapter="  SPI  ",
        page=30,
        document_type="  datasheet  ",
    )

    assert metadata.model_dump() == {
        "chip": "ESP32-S3",
        "manufacturer": "Espressif",
        "category": "MCU",
        "chapter": "SPI",
        "page": 30,
        "document_type": "datasheet",
    }


@pytest.mark.parametrize(
    "field",
    ["chip", "manufacturer", "category", "chapter", "document_type"],
)
def test_document_metadata_rejects_blank_strings(field: str) -> None:
    with pytest.raises(ValidationError):
        DocumentMetadata.model_validate({field: "   "})


def test_document_metadata_rejects_invalid_page_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentMetadata(page=0)

    with pytest.raises(ValidationError):
        DocumentMetadata(chip="ESP32-S3", protocol="SPI")


def test_sidecar_uses_complete_document_filename(tmp_path: Path) -> None:
    path = tmp_path / "spi.md"

    assert metadata_sidecar_path(path) == tmp_path / "spi.md.metadata.json"


def test_missing_sidecar_returns_empty_metadata(tmp_path: Path) -> None:
    path = tmp_path / "spi.md"

    assert load_document_metadata(path) == DocumentMetadata()


def test_sidecar_loader_validates_document_metadata(tmp_path: Path) -> None:
    path = tmp_path / "spi.md"
    sidecar = metadata_sidecar_path(path)
    sidecar.write_text(
        json.dumps(
            {
                "chip": "ESP32-S3",
                "manufacturer": "Espressif",
                "chapter": "SPI",
                "document_type": "datasheet",
            }
        ),
        encoding="utf-8",
    )

    metadata = load_document_metadata(path)

    assert metadata.chip == "ESP32-S3"
    assert metadata.chapter == "SPI"


@pytest.mark.parametrize(
    "payload",
    ["not-json", json.dumps({"page": 0}), json.dumps({"unknown": "value"})],
)
def test_invalid_sidecar_raises_metadata_error(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "spi.md"
    metadata_sidecar_path(path).write_text(payload, encoding="utf-8")

    with pytest.raises(MetadataError):
        load_document_metadata(path)


def test_sidecar_directory_raises_metadata_error(tmp_path: Path) -> None:
    path = tmp_path / "spi.md"
    metadata_sidecar_path(path).mkdir()

    with pytest.raises(MetadataError):
        load_document_metadata(path)


def test_non_utf8_sidecar_raises_metadata_error(tmp_path: Path) -> None:
    path = tmp_path / "spi.md"
    metadata_sidecar_path(path).write_bytes(b"\xff\xfe")

    with pytest.raises(MetadataError):
        load_document_metadata(path)


def test_phase2_seed_structure_has_valid_sidecars() -> None:
    knowledge_root = Path(__file__).resolve().parents[2] / "knowledge"
    relative_paths = [
        "esp32/esp32_s3/datasheet/spi_overview.md",
        "esp32/esp32_s3/esp_idf/spi_driver.md",
        "esp32/esp32_s3/examples/spi_dma.md",
        "stm32/stm32f103/reference/spi_overview.md",
        "stm32/stm32f103/hal/spi.md",
        "protocols/spi.md",
        "protocols/i2c.md",
        "protocols/uart.md",
        "freertos/tasks.md",
        "debugging/esp32_guru_meditation.md",
        "debugging/stm32_hardfault.md",
    ]

    for relative_path in relative_paths:
        document_path = knowledge_root / relative_path
        assert document_path.is_file(), relative_path
        assert metadata_sidecar_path(document_path).is_file(), relative_path
        assert load_document_metadata(document_path).document_type is not None
