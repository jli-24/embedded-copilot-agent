"""Request-scoped secure file reading and extraction boundaries."""

from embedded_copilot.file_intelligence.extractor import TemporaryFileSummary
from embedded_copilot.file_intelligence.reader import SecureFileReader
from embedded_copilot.file_intelligence.security import RootedReferenceResolver

__all__ = [
    "RootedReferenceResolver",
    "SecureFileReader",
    "TemporaryFileSummary",
]
