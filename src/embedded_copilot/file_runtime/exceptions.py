from __future__ import annotations


class FileRuntimeError(RuntimeError):
    """A safe file-runtime failure that never carries source details."""

    error_code = "file_unavailable"

    def __init__(self) -> None:
        super().__init__(self.error_code)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class FileReferenceNotFound(FileRuntimeError):
    """The requested session-bound reference does not exist."""


class FileReferenceConflict(FileRuntimeError):
    """The trusted reference no longer matches the underlying file."""


class FileRuntimeUnavailable(FileRuntimeError):
    """The runtime or requested extractor is unavailable."""


class FileAnalysisTimeout(FileRuntimeError):
    """The request-scoped file analysis exceeded its deadline."""
