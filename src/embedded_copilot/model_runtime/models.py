from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/)")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|bearer|password|credential|secret|provider)\s*[:=]",
    re.IGNORECASE,
)


def safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not text
        or len(text) > maximum
        or "\x00" in text
        or "\n" in text
        or "\r" in text
        or _PATH.search(text)
        or _SENSITIVE.search(text)
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def identifier(value: object, *, field: str) -> str:
    text = safe_text(value, field=field, maximum=128)
    if not _IDENTIFIER.fullmatch(text) or "/" in text or "\\" in text:
        raise ValueError(f"{field} is invalid")
    return text


def tuple_only(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def confidence(value: object) -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("confidence is invalid")
    return value


def canonical_fingerprint(value: Any, *, exclude: set[str]) -> str:
    payload = value.model_dump(mode="json", exclude=exclude)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
