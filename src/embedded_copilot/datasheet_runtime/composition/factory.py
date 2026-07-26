from __future__ import annotations

import asyncio
from typing import BinaryIO

from embedded_copilot.datasheet_runtime.contracts import (
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
)
from embedded_copilot.datasheet_runtime.exceptions import (
    DatasheetAnalysisTimeout,
    DatasheetRuntimeError,
    DatasheetRuntimeUnavailable,
)
from embedded_copilot.datasheet_runtime.extractors.electrical import (
    extract_electrical_candidates,
)
from embedded_copilot.datasheet_runtime.facade import DatasheetRuntime
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PDFStructureParser,
)
from embedded_copilot.datasheet_runtime.parser.section import detect_sections
from embedded_copilot.datasheet_runtime.security.policy import (
    ANALYSIS_TIMEOUT_SECONDS,
)
from embedded_copilot.file_runtime import (
    FileExtractionPort,
    FileReference,
    FileReferenceRequest,
    FileRuntimeError,
    FileType,
)


class _DatasheetExtractor:
    __slots__ = ("_parser",)

    def __init__(self) -> None:
        self._parser = PDFStructureParser()

    def extract(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> DatasheetSummary:
        structure = self._parser.parse(stream, reference=reference)
        return DatasheetSummary(
            file_id=reference.file_id,
            electrical_candidates=extract_electrical_candidates(structure),
            section_candidates=detect_sections(structure),
        )


class _DatasheetPort:
    __slots__ = ("_extractor", "_file_port")

    def __init__(self, file_port: FileExtractionPort) -> None:
        self._file_port = file_port
        self._extractor = _DatasheetExtractor()

    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        file_request = FileReferenceRequest(
            session_id=request.session_id,
            file_id=request.file_id,
            file_type=FileType.UNKNOWN,
            instruction_summary=request.instruction_summary,
        )
        try:
            summary = await asyncio.wait_for(
                self._file_port.extract(
                    file_request,
                    self._extractor,
                    result_type=DatasheetSummary,
                ),
                timeout=ANALYSIS_TIMEOUT_SECONDS,
            )
            return DatasheetResponse(summary=summary)
        except TimeoutError:
            raise DatasheetAnalysisTimeout() from None
        except asyncio.CancelledError:
            raise
        except (DatasheetRuntimeError, FileRuntimeError):
            raise
        except Exception:
            raise DatasheetRuntimeUnavailable() from None


def create_datasheet_runtime(
    file_port: FileExtractionPort,
) -> DatasheetRuntime:
    if not isinstance(file_port, FileExtractionPort):
        raise DatasheetRuntimeUnavailable()
    return DatasheetRuntime._compose(_DatasheetPort(file_port))
