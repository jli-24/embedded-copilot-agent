from __future__ import annotations

from embedded_copilot.datasheet_runtime.contracts import (
    DatasheetIntelligencePort,
)
from embedded_copilot.file_runtime import FileExtractionPort


class DatasheetRuntime:
    __slots__ = ("_datasheet_port",)

    def __init__(self, file_port: FileExtractionPort) -> None:
        raise TypeError("DatasheetRuntime must be created by the composition factory")

    @classmethod
    def _compose(
        cls,
        datasheet_port: DatasheetIntelligencePort,
    ) -> "DatasheetRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_datasheet_port", datasheet_port)
        return runtime

    def datasheet_port(self) -> DatasheetIntelligencePort:
        return self._datasheet_port
