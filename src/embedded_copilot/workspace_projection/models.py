from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if not text or not _ID.fullmatch(text) or "/" in text or "\\" in text:
        raise ValueError(f"{field} is invalid")
    return text


def filename(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("filename is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not _FILE.fullmatch(text)
        or text in {".", ".."}
        or text.casefold().startswith(".env")
        or text.casefold() == ".git"
    ):
        raise ValueError("filename is invalid")
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
