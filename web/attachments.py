from __future__ import annotations

from pathlib import PurePath
from typing import Protocol

from embedded_copilot.input.classifier import AttachmentClassifier
from embedded_copilot.input.models import UserAttachment


class UploadedFileMetadata(Protocol):
    name: str
    type: str | None
    size: int


def build_attachment_metadata(
    uploaded: UploadedFileMetadata,
    attachment_id: str,
) -> UserAttachment:
    """Build an attachment contract without opening uploaded content."""
    content_type = uploaded.type or AttachmentClassifier.canonical_content_type(
        uploaded.name
    )
    media_type = AttachmentClassifier.classify(uploaded.name, content_type)
    return UserAttachment(
        id=attachment_id,
        filename=uploaded.name,
        media_type=media_type,
        content_type=AttachmentClassifier.canonical_content_type(uploaded.name),
        size_bytes=uploaded.size,
        metadata={
            "category": media_type.value,
            "format": PurePath(uploaded.name).suffix.removeprefix(".").casefold(),
        },
    )
