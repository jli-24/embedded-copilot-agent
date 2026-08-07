from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from pydantic import BaseModel

_IDENTIFIER_START = re.compile(r"^[A-Za-z0-9]$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_UNSAFE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|https?://|\x00|\r|\n|"
    r"raw\s+image|raw\s+pdf|binary|stdout|stderr|raw\s+log|serial\s+dump|"
    r"command|environment|credential|token|provider|runtime|stack\s*trace|"
    r"prompt|cot|patch|workspace\s+mutation)",
    re.IGNORECASE,
)


def identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    text = safe_text(value, field=field, maximum=160)
    if (
        not _IDENTIFIER_START.fullmatch(text[0])
        or text.casefold() in {".env", ".git"}
        or any(
            not (
                (char.isascii() and (char.isalnum() or char in "._:#-"))
                or unicodedata.category(char).startswith("L")
            )
            for char in text[1:]
        )
    ):
        raise ValueError(f"{field} is invalid")
    return text


def safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or len(text) > maximum or _UNSAFE.search(text):
        raise ValueError(f"{field} is unsafe")
    return text


def tuple_only(value: object, *, field: str) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not _FINGERPRINT.fullmatch(text):
        raise ValueError(f"{field} is invalid")
    return text


def confidence(value: object, *, field: str = "confidence") -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, float)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{field} is invalid")
    return value


def canonical_fingerprint(value: BaseModel, *, exclude: set[str] | None = None) -> str:
    payload = value.model_dump(mode="json", exclude=exclude or set())
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "canonical_fingerprint",
    "confidence",
    "fingerprint",
    "identifier",
    "safe_text",
    "tuple_only",
]
