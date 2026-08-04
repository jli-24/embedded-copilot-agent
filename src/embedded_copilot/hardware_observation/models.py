from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")


def identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or not _ID.fullmatch(text) or "/" in text or "\\" in text:
        raise ValueError(f"{field} is invalid")
    return text


def safe_text(
    value: object, *, field: str, maximum: int = 512, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (not allow_empty and not text) or len(text) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(char in text for char in ("\x00", "\r", "\n")):
        raise ValueError(f"{field} is unsafe")
    if re.search(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/)", text):
        raise ValueError(f"{field} is unsafe")
    if re.search(
        r"(?:password|credential|secret|token|api[_ -]?key|provider|environment|command|traceback|exception|raw[_ -]?log)\s*[:=]?",
        text,
        re.I,
    ):
        raise ValueError(f"{field} is unsafe")
    return text


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
