import json
from pathlib import Path

import pytest

from embedded_copilot.firmware.exceptions import FirmwareKnowledgeError
from embedded_copilot.firmware.knowledge.loader import FirmwareDocumentLoader


def test_loader_reads_markdown_and_infers_metadata(tmp_path: Path) -> None:
    document_path = tmp_path / "esp32" / "esp-idf" / "wifi.md"
    document_path.parent.mkdir(parents=True)
    document_path.write_text("# WiFi Guide\nESP32 ESP-IDF WiFi notes", encoding="utf-8")

    documents = FirmwareDocumentLoader().load(tmp_path)

    assert len(documents) == 1
    assert documents[0].title == "WiFi Guide"
    assert documents[0].platform == "ESP32"
    assert documents[0].framework == "ESP-IDF"
    assert documents[0].metadata["source"] == "esp32/esp-idf/wifi.md"
    assert str(tmp_path) not in str(documents[0].metadata)


def test_loader_uses_txt_sidecar_and_ignores_other_files(tmp_path: Path) -> None:
    document_path = tmp_path / "camera.txt"
    document_path.write_text("Camera SDK notes", encoding="utf-8")
    sidecar_path = tmp_path / "camera.txt.metadata.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "title": "Camera SDK",
                "platform": "ESP32",
                "framework": "ESP-IDF",
                "metadata": {"license": "original-test-seed"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "ignored.bin").write_bytes(b"ignored")

    documents = FirmwareDocumentLoader().load(tmp_path)

    assert [document.title for document in documents] == ["Camera SDK"]
    assert documents[0].metadata["license"] == "original-test-seed"
    assert documents[0].metadata["file_type"] == "txt"


@pytest.mark.parametrize("failure", ["invalid_sidecar", "empty", "unknown_metadata"])
def test_loader_reports_invalid_documents(tmp_path: Path, failure: str) -> None:
    document_path = tmp_path / "guide.md"
    if failure == "empty":
        document_path.write_text("", encoding="utf-8")
    else:
        document_path.write_text("# Guide\ncontent", encoding="utf-8")
    if failure == "invalid_sidecar":
        (tmp_path / "guide.md.metadata.json").write_text("{", encoding="utf-8")

    with pytest.raises(FirmwareKnowledgeError):
        FirmwareDocumentLoader().load(tmp_path)


def test_loader_ids_are_stable(tmp_path: Path) -> None:
    path = tmp_path / "stm32_hal.txt"
    path.write_text("STM32 HAL UART", encoding="utf-8")
    loader = FirmwareDocumentLoader()

    first = loader.load(tmp_path)[0]
    second = loader.load(tmp_path)[0]

    assert first.id == second.id


def test_loader_maps_blank_sidecar_fields_to_knowledge_error(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("ESP32 ESP-IDF content", encoding="utf-8")
    (tmp_path / "guide.md.metadata.json").write_text(
        json.dumps(
            {
                "title": " ",
                "platform": "ESP32",
                "framework": "ESP-IDF",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FirmwareKnowledgeError):
        FirmwareDocumentLoader().load(tmp_path)
