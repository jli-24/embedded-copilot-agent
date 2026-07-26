"""Read-only secure file intelligence runtime."""

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    FileIntelligencePort,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceCatalog,
    FileReferenceRequest,
    FileType,
)
from embedded_copilot.file_runtime.exceptions import (
    FileAnalysisTimeout,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileRuntimeError,
    FileRuntimeUnavailable,
)
from embedded_copilot.file_runtime.facade import FileRuntime

__all__ = [
    "DocumentSummary",
    "FileAnalysisTimeout",
    "FileIntelligencePort",
    "FileIntelligenceResponse",
    "FileReference",
    "FileReferenceCatalog",
    "FileReferenceConflict",
    "FileReferenceNotFound",
    "FileReferenceRequest",
    "FileRuntime",
    "FileRuntimeError",
    "FileRuntimeUnavailable",
    "FileType",
]
