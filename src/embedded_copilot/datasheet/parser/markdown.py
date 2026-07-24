from __future__ import annotations

from embedded_copilot.datasheet.exceptions import DatasheetParseError
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.datasheet.parser.base import (
    DEFAULT_MAX_DATASHEET_SIZE_BYTES,
    DatasheetSourceResolver,
    read_datasheet_source,
    validate_parser_limit,
)
from embedded_copilot.datasheet.parser.rules import extract_datasheet_model
from embedded_copilot.input.models import UserAttachment


DEFAULT_MAX_DATASHEET_TEXT_CHARS = 2_000_000


class MarkdownDatasheetParser:
    """Parse a bounded Markdown subset into structured evidence."""

    def __init__(
        self,
        resolver: DatasheetSourceResolver,
        *,
        max_size_bytes: int = DEFAULT_MAX_DATASHEET_SIZE_BYTES,
        max_text_chars: int = DEFAULT_MAX_DATASHEET_TEXT_CHARS,
    ) -> None:
        if not isinstance(resolver, DatasheetSourceResolver):
            raise DatasheetParseError("Datasheet source resolver is invalid")
        self._resolver = resolver
        self._max_size_bytes = validate_parser_limit(
            max_size_bytes,
            label="size",
        )
        self._max_text_chars = validate_parser_limit(
            max_text_chars,
            label="text",
        )

    def parse(self, attachment: UserAttachment) -> UnifiedDatasheetModel:
        try:
            raw = read_datasheet_source(
                attachment,
                self._resolver,
                suffix=".md",
                content_type="text/markdown",
                metadata_format="md",
                max_size_bytes=self._max_size_bytes,
            )
            text = raw.decode("utf-8", errors="strict")
            if not text.strip() or "\x00" in text or len(text) > self._max_text_chars:
                raise ValueError("invalid text")
            return extract_datasheet_model(text, source_format="markdown")
        except DatasheetParseError:
            raise
        except Exception:
            raise DatasheetParseError("Markdown Datasheet parsing failed") from None
