from __future__ import annotations

import asyncio
import io

import fitz
import pytest

from embedded_copilot.datasheet_runtime import (
    DatasheetAnalysisTimeout,
    DatasheetDocumentRejected,
    DatasheetRequest,
    DatasheetSummary,
    create_datasheet_runtime,
)
from embedded_copilot.datasheet_runtime.extractors.electrical import (
    extract_electrical_candidates,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PDFStructureParser,
    PdfPageStructure,
    PdfStructure,
)
from embedded_copilot.datasheet_runtime.parser.table import (
    TableStructure,
    detect_tables,
)
from embedded_copilot.file_runtime import (
    FileReference,
    FileReferenceRequest,
    FileType,
)


def _pdf(*lines: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    if lines:
        page.insert_text((72, 72), "\n".join(lines))
    payload = document.tobytes()
    document.close()
    return payload


def _encrypted_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Electrical Characteristics")
    payload = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()
    return payload


def _reference(payload: bytes) -> FileReference:
    return FileReference(
        session_id="session:1",
        file_id="file:1",
        basename="datasheet.pdf",
        document_type=FileType.PDF,
        size_bytes=len(payload),
        relative_path="datasheet.pdf",
    )


class _MemoryExtractionPort:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.request: FileReferenceRequest | None = None

    async def extract(self, request, extractor, *, result_type):
        self.request = request
        result = extractor.extract(
            io.BytesIO(self.payload),
            reference=_reference(self.payload),
        )
        assert type(result) is result_type
        return result.model_copy(deep=True)


def _request() -> DatasheetRequest:
    return DatasheetRequest(
        session_id="session:1",
        file_id="file:1",
        instruction_summary="Extract unverified candidates.",
    )


def test_pdf_runtime_returns_only_candidate_dtos() -> None:
    payload = _pdf(
        "STM32F103C8T6 Datasheet",
        "Communication interfaces: SPI, UART and I2C",
        "1 Electrical Characteristics",
        "Operating voltage range: 2000 mV to 3600 mV",
        "Operating temperature: -40 C to 85 C",
        "Current range: 10 mA to 120 mA",
        "2 Functional Description",
    )
    source_port = _MemoryExtractionPort(payload)
    runtime = create_datasheet_runtime(source_port)

    response = asyncio.run(runtime.datasheet_port().analyze(_request()))

    assert source_port.request == FileReferenceRequest(
        session_id="session:1",
        file_id="file:1",
        file_type=FileType.UNKNOWN,
        instruction_summary="Extract unverified candidates.",
    )
    assert response.summary == DatasheetSummary(
        file_id="file:1",
        component_candidate={
            "semantics": "candidate",
            "family": "STM32",
            "model": "STM32F103C8T6",
        },
        interface_candidates=(
            {"semantics": "candidate", "name": "UART"},
            {"semantics": "candidate", "name": "SPI"},
            {"semantics": "candidate", "name": "I2C"},
        ),
        electrical_candidates=(
            {
                "semantics": "candidate",
                "kind": "voltage_range",
                "minimum": 2.0,
                "maximum": 3.6,
                "unit": "V",
            },
            {
                "semantics": "candidate",
                "kind": "operating_temperature",
                "minimum": -40.0,
                "maximum": 85.0,
                "unit": "degC",
            },
            {
                "semantics": "candidate",
                "kind": "current_range",
                "minimum": 0.01,
                "maximum": 0.12,
                "unit": "A",
            },
        ),
        section_candidates=(
            {
                "semantics": "candidate",
                "name": "Electrical Characteristics",
            },
            {
                "semantics": "candidate",
                "name": "Functional Description",
            },
        ),
    )
    serialized = response.model_dump_json()
    assert "Operating voltage" not in serialized
    assert "Functional Description" in serialized
    assert "engineering_fact" not in serialized
    assert "candidate" in serialized


@pytest.mark.parametrize(
    "payload",
    (
        pytest.param(b"not-a-pdf", id="malformed"),
        pytest.param(_encrypted_pdf(), id="encrypted"),
        pytest.param(
            b"%PDF-" + (b"x" * (25 * 1024 * 1024)),
            id="oversized",
        ),
    ),
)
def test_pdf_parser_rejects_malformed_encrypted_and_oversized_without_leaks(
    payload: bytes,
) -> None:
    runtime = create_datasheet_runtime(_MemoryExtractionPort(payload))

    with pytest.raises(DatasheetDocumentRejected) as raised:
        asyncio.run(runtime.datasheet_port().analyze(_request()))

    assert str(raised.value) == "datasheet_unavailable"
    assert "password" not in str(raised.value)
    assert "pdf" not in str(raised.value).casefold()
    assert "path" not in str(raised.value).casefold()


def test_pdf_without_text_layer_returns_empty_candidate_summary() -> None:
    runtime = create_datasheet_runtime(_MemoryExtractionPort(_pdf()))

    response = asyncio.run(runtime.datasheet_port().analyze(_request()))

    assert response.summary == DatasheetSummary(file_id="file:1")
    assert response.review_required is True


def test_table_detection_feeds_normalized_electrical_candidates() -> None:
    class _Table:
        def extract(self):
            return [
                ["Parameter", "Min", "Max", "Unit"],
                ["Operating voltage range", "1.8", "3.6", "V"],
                ["Operating temperature", "-40", "105", "C"],
                ["Current range", "5", "50", "mA"],
            ]

    class _Finder:
        tables = (_Table(),)

    class _Page:
        def find_tables(self):
            return _Finder()

    tables = detect_tables(_Page())
    structure = PdfStructure(
        page_count=1,
        pages=(
            PdfPageStructure(
                page_number=1,
                text="",
                tables=tables,
            ),
        ),
    )

    candidates = extract_electrical_candidates(structure)

    assert tables == (
        TableStructure(
            rows=(
                ("Parameter", "Min", "Max", "Unit"),
                ("Operating voltage range", "1.8", "3.6", "V"),
                ("Operating temperature", "-40", "105", "C"),
                ("Current range", "5", "50", "mA"),
            )
        ),
    )
    assert tuple(
        (item.semantics, item.kind, item.minimum, item.maximum, item.unit)
        for item in candidates
    ) == (
        ("candidate", "voltage_range", 1.8, 3.6, "V"),
        ("candidate", "operating_temperature", -40.0, 105.0, "degC"),
        ("candidate", "current_range", 0.005, 0.05, "A"),
    )


def test_parser_caps_page_count_and_extracted_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import embedded_copilot.datasheet_runtime.parser.pdf_structure as parser_module

    monkeypatch.setattr(parser_module, "MAX_EXTRACTED_CHARACTERS", 8)
    payload = _pdf("Electrical Characteristics")
    parser = PDFStructureParser()

    with pytest.raises(DatasheetDocumentRejected):
        parser.parse(io.BytesIO(payload), reference=_reference(payload))


def test_parser_caps_page_count(monkeypatch: pytest.MonkeyPatch) -> None:
    import embedded_copilot.datasheet_runtime.parser.pdf_structure as parser_module

    document = fitz.open()
    document.new_page()
    document.new_page()
    payload = document.tobytes()
    document.close()
    monkeypatch.setattr(parser_module, "MAX_PDF_PAGES", 1)

    with pytest.raises(DatasheetDocumentRejected):
        PDFStructureParser().parse(
            io.BytesIO(payload),
            reference=_reference(payload),
        )


def test_runtime_maps_timeout_and_propagates_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import embedded_copilot.datasheet_runtime.composition.factory as factory_module

    class _SlowPort:
        cancelled = False

        async def extract(self, request, extractor, *, result_type):
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    monkeypatch.setattr(factory_module, "ANALYSIS_TIMEOUT_SECONDS", 0.001)
    slow_port = _SlowPort()
    runtime = create_datasheet_runtime(slow_port)

    with pytest.raises(DatasheetAnalysisTimeout):
        asyncio.run(runtime.datasheet_port().analyze(_request()))
    assert slow_port.cancelled is True
