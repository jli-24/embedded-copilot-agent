import pytest
from pydantic import ValidationError

from embedded_copilot.firmware.knowledge.models import FirmwareDocument


def test_firmware_document_strips_required_strings() -> None:
    document = FirmwareDocument(
        id=" doc-1 ",
        title=" GPIO Guide ",
        platform=" ESP32 ",
        framework=" ESP-IDF ",
        content=" content ",
    )

    assert document.id == "doc-1"
    assert document.title == "GPIO Guide"
    assert document.content == "content"


def test_firmware_document_rejects_empty_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        FirmwareDocument(
            id="",
            title="guide",
            platform="ESP32",
            framework="ESP-IDF",
            content="content",
        )
    with pytest.raises(ValidationError):
        FirmwareDocument(
            id="1",
            title="guide",
            platform="ESP32",
            framework="ESP-IDF",
            content="content",
            extra=True,
        )
