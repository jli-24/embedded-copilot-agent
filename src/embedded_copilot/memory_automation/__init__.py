from .classifier import classify_memory
from .contracts import (
    MemoryApprovalProjection,
    MemoryCandidate,
    MemoryReviewStatus,
    MemorySourceKind,
    MemorySourceProjection,
    MemorySourceType,
    MemoryType,
    VersionMemoryInput,
    VersionMemoryProjection,
)
from .factory import create_memory_automation
from .projector import project_candidate
from .service import MemoryAutomationPort, MemoryAutomationService
from .exceptions import MemoryApprovalRejected, MemoryAutomationError, MemoryProjectionRejected

__all__ = [
    "MemoryApprovalProjection",
    "MemoryAutomationPort",
    "MemoryAutomationService",
    "MemoryAutomationError",
    "MemoryApprovalRejected",
    "MemoryProjectionRejected",
    "MemoryCandidate",
    "MemoryReviewStatus",
    "MemorySourceKind",
    "MemorySourceProjection",
    "MemorySourceType",
    "MemoryType",
    "VersionMemoryInput",
    "VersionMemoryProjection",
    "classify_memory",
    "create_memory_automation",
    "project_candidate",
]
