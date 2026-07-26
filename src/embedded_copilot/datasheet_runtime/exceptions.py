from __future__ import annotations


class DatasheetRuntimeError(RuntimeError):
    """A safe datasheet-runtime failure without document details."""

    error_code = "datasheet_unavailable"

    def __init__(self) -> None:
        super().__init__(self.error_code)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class DatasheetDocumentRejected(DatasheetRuntimeError):
    """The referenced document cannot be safely analyzed."""


class DatasheetRuntimeUnavailable(DatasheetRuntimeError):
    """The runtime is not configured or cannot complete analysis."""


class DatasheetAnalysisTimeout(DatasheetRuntimeError):
    """The request-scoped analysis exceeded its fixed deadline."""
