from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Any

from pydantic import BaseModel

_FINGERPRINT = re.compile(r"sha256:[a-f0-9]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}")
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)", re.IGNORECASE)


def safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (
        not normalized
        or len(normalized) > maximum
        or "\x00" in normalized
        or "\n" in normalized
        or "\r" in normalized
        or _SENSITIVE.search(normalized)
        or _ABSOLUTE_PATH.search(normalized)
        or "../" in normalized
        or "..\\" in normalized
    ):
        raise ValueError(f"{field} is unsafe")
    return normalized


def identifier(value: object, *, field: str) -> str:
    normalized = safe_text(value, field=field, maximum=160)
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"{field} is invalid")
    return normalized


def filename(value: object) -> str:
    normalized = safe_text(value, field="filename", maximum=128)
    if (
        not _FILENAME.fullmatch(normalized)
        or normalized in {".", ".."}
        or normalized.startswith(".")
        or normalized.lower() in {".env", "secrets", "credentials"}
    ):
        raise ValueError("filename is invalid")
    return normalized


def tuple_only(value: object, *, field: str) -> object:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    return value


def finite_confidence(value: object, *, field: str = "confidence") -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} is invalid")
    return value


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise ValueError(f"{field} is invalid")
    return value


def canonical_fingerprint(value: BaseModel, *, exclude: set[str]) -> str:
    encoded = json.dumps(
        value.model_dump(mode="json", exclude=exclude),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def as_material(value: BaseModel, *, exclude: set[str]) -> dict[str, Any]:
    return value.model_dump(mode="json", exclude=exclude)
