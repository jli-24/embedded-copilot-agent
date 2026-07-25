from __future__ import annotations

from pathlib import Path

from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.engineering.adapter import RealEngineeringInputAdapter
from embedded_copilot.engineering.resolver import TrustedEngineeringResolver
from embedded_copilot.firmware.review.analyzer import FirmwareReviewAnalyzer
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)

from tests.engineering.fixtures import datasheet_model


class _PDFParser:
    def parse(self, raw_pdf: bytes, *, source_id: str) -> UnifiedDatasheetModel:
        assert raw_pdf == b"%PDF-real-input"
        return datasheet_model().model_copy(
            update={"metadata": {"source_id": source_id}}
        )


def _attachment(
    attachment_id: str,
    path: Path,
    media_type: AttachmentType,
    content_type: str,
) -> UserAttachment:
    return UserAttachment(
        id=attachment_id,
        filename=path.name,
        media_type=media_type,
        content_type=content_type,
        size_bytes=path.stat().st_size,
        metadata={
            "category": media_type.value,
            "format": path.suffix.removeprefix(".").casefold(),
        },
    )


def test_real_input_adapter_returns_sanitized_immutable_envelope(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "esp32.pdf"
    source = tmp_path / "camera.c"
    pdf.write_bytes(b"%PDF-real-input")
    source.write_text(
        "void camera_init(void) { camera_config_t c = {.pin_d0 = GPIO_NUM_8}; }",
        encoding="utf-8",
    )
    context = UnifiedInputContext(
        attachments=(
            _attachment(
                "datasheet-1",
                pdf,
                AttachmentType.DOCUMENT,
                "application/pdf",
            ),
            _attachment(
                "source-1",
                source,
                AttachmentType.SOURCE_CODE,
                "text/x-c",
            ),
        )
    )
    adapter = RealEngineeringInputAdapter(
        resolver=TrustedEngineeringResolver(tmp_path),
        pdf_parser=_PDFParser(),
        firmware_analyzer=FirmwareReviewAnalyzer(),
    )

    envelope = adapter.adapt(context)

    assert envelope.datasheet is not None
    assert envelope.firmware_review is not None
    assert envelope.errors == ()
    serialized = envelope.model_dump_json()
    assert "%PDF-real-input" not in serialized
    assert "camera_config_t" not in serialized
    assert str(tmp_path) not in serialized


def test_real_input_adapter_keeps_valid_datasheet_when_firmware_resolution_fails(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "esp32.pdf"
    source = tmp_path / "camera.c"
    pdf.write_bytes(b"%PDF-real-input")
    source.write_text("void app_main(void) {}", encoding="utf-8")
    datasheet_attachment = _attachment(
        "datasheet-1",
        pdf,
        AttachmentType.DOCUMENT,
        "application/pdf",
    )
    invalid_source = _attachment(
        "source-1",
        source,
        AttachmentType.SOURCE_CODE,
        "text/x-c",
    ).model_copy(update={"size_bytes": source.stat().st_size + 1})
    adapter = RealEngineeringInputAdapter(
        resolver=TrustedEngineeringResolver(tmp_path),
        pdf_parser=_PDFParser(),
        firmware_analyzer=FirmwareReviewAnalyzer(),
    )

    envelope = adapter.adapt(
        UnifiedInputContext(
            attachments=(datasheet_attachment, invalid_source),
        )
    )

    assert envelope.datasheet is not None
    assert envelope.firmware_review is None
    assert [(item.domain, item.code) for item in envelope.errors] == [
        ("firmware", "source_resolution_failed")
    ]
