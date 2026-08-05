from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:password|credential|secret|token|api[_ -]?key|authorization)\s*[:=]",
    re.IGNORECASE,
)


def identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or not _ID.fullmatch(text) or "/" in text or "\\" in text:
        raise ValueError(f"{field} is invalid")
    return text


def safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not text
        or len(text) > maximum
        or any(char in text for char in ("\x00", "\r", "\n"))
        or re.search(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/)", text)
        or _SENSITIVE.search(text)
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def optional_safe_text(value: object, *, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return safe_text(value, field=field, maximum=maximum)


def fingerprint(value: object) -> str:
    if not isinstance(value, str) or not _FP.fullmatch(value):
        raise ValueError("fingerprint is invalid")
    return value


def canonical_fingerprint(value: Any, *, exclude: set[str]) -> str:
    encoded = json.dumps(
        value.model_dump(mode="json", exclude=exclude),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
