from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Iterable

from pydantic import BaseModel

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)", re.IGNORECASE
)
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}",
    re.IGNORECASE,
)


def normalize_text(
    value: object,
    *,
    field: str,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    result = unicodedata.normalize("NFC", value.strip())
    if (
        (not result and not allow_empty)
        or len(result) > maximum
        or any(char in result for char in ("\x00", "\r", "\n"))
        or _ABSOLUTE_PATH.search(result)
        or _SENSITIVE.search(result)
    ):
        raise ValueError(f"{field} is unsafe")
    return result


def identifier(value: object, *, field: str) -> str:
    result = normalize_text(value, field=field, maximum=160)
    if _IDENTIFIER.fullmatch(result) is None:
        raise ValueError(f"{field} is invalid")
    return result


def tuple_only(value: object, *, field: str) -> tuple[object, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    return copy.deepcopy(value)


def fingerprint(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def confidence(value: object, *, field: str = "confidence") -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} is invalid")
    return value


def checked_instance(value: object, model: type[BaseModel], *, field: str) -> BaseModel:
    if type(value) is not model:
        raise TypeError(f"{field} must be a typed projection")
    return model.model_validate(copy.deepcopy(value))


def canonical_fingerprint(
    value: BaseModel,
    *,
    exclude: set[str] | None = None,
) -> str:
    material = value.model_dump(mode="json", exclude=exclude or set())
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def checked_text_tuple(
    value: object,
    *,
    field: str,
    maximum_items: int,
    maximum_length: int,
) -> tuple[str, ...]:
    items = tuple_only(value, field=field)
    if len(items) > maximum_items:
        raise ValueError(f"{field} is invalid")
    result = tuple(
        normalize_text(item, field=field, maximum=maximum_length) for item in items
    )
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must be unique")
    return result


def checked_identifier_tuple(
    value: object,
    *,
    field: str,
    maximum_items: int,
) -> tuple[str, ...]:
    items = tuple_only(value, field=field)
    if len(items) > maximum_items:
        raise ValueError(f"{field} is invalid")
    result = tuple(identifier(item, field=field) for item in items)
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must be unique")
    return result


def no_iterable_conversion(value: object) -> Iterable[object]:
    return value  # pragma: no cover - typing helper only
