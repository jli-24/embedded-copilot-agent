"""Stable immutable file-runtime contracts."""

from embedded_copilot.file_runtime.contracts.models import (
    DocumentSummary,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceRequest,
    FileType,
)
from embedded_copilot.file_runtime.contracts.protocols import (
    Extractor,
    FileIntelligencePort,
    FileReferenceCatalog,
)

__all__ = [
    "DocumentSummary",
    "Extractor",
    "FileIntelligencePort",
    "FileIntelligenceResponse",
    "FileReference",
    "FileReferenceCatalog",
    "FileReferenceRequest",
    "FileType",
]
