from __future__ import annotations

import re
from pathlib import PurePosixPath


_MAX_REPORT_TEXT_LENGTH = 512
_ABSOLUTE_WINDOWS_PATH = re.compile(
    r"(?:^|[\s\"'=:(])(?:[A-Za-z]:[\\/]|\\\\)[^\s]*"
)
_ABSOLUTE_POSIX_PATH = re.compile(
    r"(?:^|[\s\"'=:(])/(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+"
)
_URI = re.compile(
    r"\b(?:(?:file|ftp|git|http|https|s3|ssh):/{1,2}|mailto:)[^\s]+",
    re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"\b(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|access[_-]?key|authorization|"
    r"credential|password|secret|token)\b\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(r"\bbearer\s+\S+", re.IGNORECASE)
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
    r"sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b"
)
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]<>|])")
_MARKDOWN_LINE_PREFIX = re.compile(r"^([#>+\-])")


def is_safe_report_text(value: str) -> bool:
    candidate = value.strip()
    if not candidate or len(candidate) > _MAX_REPORT_TEXT_LENGTH:
        return False
    if any(character in candidate for character in ("\r", "\n", "\x00")):
        return False
    return not any(
        pattern.search(candidate)
        for pattern in (
            _ABSOLUTE_WINDOWS_PATH,
            _ABSOLUTE_POSIX_PATH,
            _URI,
            _CREDENTIAL_ASSIGNMENT,
            _BEARER_TOKEN,
            _KNOWN_TOKEN,
        )
    )


def safe_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    return candidate if is_safe_report_text(candidate) else None


def safe_text_items(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        candidate
        for value in values
        if (candidate := safe_optional_text(value)) is not None
    )


def is_safe_relative_path(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    if not normalized or not is_safe_report_text(normalized):
        return False
    if re.match(r"^(?:[A-Za-z]:/|//|/|file://)", normalized, re.IGNORECASE):
        return False
    return ".." not in PurePosixPath(normalized).parts


def safe_source_fragment(value: str, *, fallback: str) -> str:
    candidate = value.strip()
    if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", candidate):
        return candidate
    return fallback


def escape_markdown(value: str) -> str:
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", value)
    return _MARKDOWN_LINE_PREFIX.sub(r"\\\1", escaped)
