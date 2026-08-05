from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")


def identifier(value: object, *, field: str, maximum: int = 128) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or len(text) > maximum or not _ID.fullmatch(text):
        raise ValueError(f"{field} is invalid")
    return text


def safe_text(value: object, *, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not text
        or len(text) > maximum
        or any(char in text for char in ("\x00", "\r", "\n"))
        or re.search(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/)", text)
        or re.search(
            r"(?:prompt|token|secret|password|credential|provider|command|exception|path)",
            text,
            re.I,
        )
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def utc_datetime(value: object, *, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field} is invalid") from error
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def canonical_fingerprint(value: Any, *, exclude: set[str]) -> str:
    encoded = json.dumps(
        value.model_dump(mode="json", exclude=exclude),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
