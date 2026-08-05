from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from pydantic import BaseModel

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|https?://|ssh://|git://|/(?:[^/\s]+/)+)",
    re.I,
)
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|bearer|password|credential|secret|token|command|prompt|stack|log)\s*[:=]",
    re.I,
)
_FORBIDDEN_CONTENT = re.compile(
    r"\b(?:raw\s+logs?|compiler\s+output|serial\s+dump|exception(?:\s+stack)?|stdout|stderr|provider|environment|credential|token|command|prompt|cot|logs?)\b",
    re.I,
)


def identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not _ID.fullmatch(text):
        raise ValueError(f"{field} is invalid")
    return text


def safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not text
        or len(text) > maximum
        or any(ch in text for ch in ("\x00", "\r", "\n"))
        or _PATH.search(text)
        or _SENSITIVE.search(text)
        or _FORBIDDEN_CONTENT.search(text)
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FP.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


def tuple_only(value: object, *, field: str) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
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


__all__ = ["canonical_fingerprint", "fingerprint", "identifier", "safe_text", "tuple_only"]
