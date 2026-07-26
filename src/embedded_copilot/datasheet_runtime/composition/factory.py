from __future__ import annotations

from embedded_copilot.datasheet_runtime.contracts import (
    DatasheetRequest,
    DatasheetResponse,
)
from embedded_copilot.datasheet_runtime.exceptions import (
    DatasheetRuntimeUnavailable,
)
from embedded_copilot.datasheet_runtime.facade import DatasheetRuntime
from embedded_copilot.file_runtime import FileExtractionPort


class _UnavailableDatasheetPort:
    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        raise DatasheetRuntimeUnavailable()


def create_datasheet_runtime(
    file_port: FileExtractionPort,
) -> DatasheetRuntime:
    if not isinstance(file_port, FileExtractionPort):
        raise DatasheetRuntimeUnavailable()
    return DatasheetRuntime._compose(_UnavailableDatasheetPort())
