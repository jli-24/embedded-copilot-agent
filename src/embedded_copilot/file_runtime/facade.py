from __future__ import annotations

from embedded_copilot.file_runtime.contracts import FileIntelligencePort


class FileRuntime:
    __slots__ = ("_file_port",)

    def __init__(self, file_port: FileIntelligencePort) -> None:
        raise TypeError("FileRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, file_port: FileIntelligencePort) -> "FileRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_file_port", file_port)
        return runtime

    def file_port(self) -> FileIntelligencePort:
        return self._file_port
