"""Safe metadata-only engineering input contracts."""

from embedded_copilot.input.classifier import AttachmentClassifier
from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.loader import InputLoader
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)

__all__ = [
    "AttachmentClassifier",
    "AttachmentType",
    "InputValidationError",
    "InputLoader",
    "UnifiedInputContext",
    "UserAttachment",
]
