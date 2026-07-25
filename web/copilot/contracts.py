from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

JsonObject = dict[str, Any]


def object_value(value: object) -> JsonObject:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def object_list(value: object) -> tuple[JsonObject, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(object_value(item) for item in value if isinstance(item, Mapping))


def text_value(value: object, *, fallback: str = "Unavailable") -> str:
    if not isinstance(value, str):
        return fallback
    candidate = " ".join(value.split())
    return candidate or fallback


def integer_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)
