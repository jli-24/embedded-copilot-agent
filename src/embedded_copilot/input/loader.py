from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from embedded_copilot.input.classifier import AttachmentClassifier
from embedded_copilot.input.exceptions import InputValidationError
from embedded_copilot.input.models import UserAttachment
from embedded_copilot.input.validators import (
    validate_input_root,
    validate_relative_file,
)


DEFAULT_MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024


class InputLoader:
    """Load safe attachment metadata without opening file contents."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_size_bytes: int = DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
    ) -> None:
        if (
            isinstance(max_size_bytes, bool)
            or not isinstance(max_size_bytes, int)
            or max_size_bytes <= 0
        ):
            raise InputValidationError("input size limit is invalid")
        self._root = validate_input_root(root)
        self._max_size_bytes = max_size_bytes

    def load(
        self,
        relative_path: str | Path,
        *,
        attachment_id: str,
        content_type: str | None = None,
    ) -> UserAttachment:
        path, file_stat = validate_relative_file(self._root, relative_path)
        if file_stat.st_size <= 0 or file_stat.st_size > self._max_size_bytes:
            raise InputValidationError("attachment size is invalid")

        attachment_type = AttachmentClassifier.classify(path.name, content_type)
        canonical_content_type = AttachmentClassifier.canonical_content_type(
            path.name
        )
        try:
            return UserAttachment(
                id=attachment_id,
                filename=path.name,
                media_type=attachment_type,
                content_type=canonical_content_type,
                size_bytes=file_stat.st_size,
                metadata={
                    "category": attachment_type.value,
                    "format": path.suffix.removeprefix(".").casefold(),
                },
            )
        except ValidationError:
            raise InputValidationError("attachment metadata is invalid") from None
