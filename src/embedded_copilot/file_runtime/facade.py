from __future__ import annotations

from embedded_copilot.file_runtime.contracts import (
    FileExtractionPort,
    FileIntelligencePort,
)


class FileRuntime:
    __slots__ = ("_extraction_port", "_file_port")

    def __init__(
        self,
        file_port: FileIntelligencePort,
        extraction_port: FileExtractionPort | None = None,
    ) -> None:
        raise TypeError("FileRuntime must be created by the composition factory")

    @classmethod
    def _compose(
        cls,
        file_port: FileIntelligencePort,
        extraction_port: FileExtractionPort,
    ) -> "FileRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_file_port", file_port)
        object.__setattr__(runtime, "_extraction_port", extraction_port)
        return runtime

    def file_port(self) -> FileIntelligencePort:
        return self._file_port

    def extraction_port(self) -> FileExtractionPort:
        return self._extraction_port
