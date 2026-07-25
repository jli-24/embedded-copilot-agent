from __future__ import annotations

import copy
import re
from collections.abc import Sequence

from pydantic import ConfigDict

from embedded_copilot.schemas.result import ContractModel

_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)",
    re.IGNORECASE,
)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


class HardwareDesignModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def safe_text(value: object, *, field: str, max_length: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > max_length
        or any(char in candidate for char in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def safe_optional_text(
    value: object,
    *,
    field: str,
    max_length: int = 512,
) -> str | None:
    if value is None:
        return None
    return safe_text(value, field=field, max_length=max_length)


def safe_identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def tuple_values(value: object) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return value
    return tuple(copy.deepcopy(value))


def source_ids(value: object) -> object:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return value
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = safe_identifier(item, field="source_id")
        key = candidate.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(candidate)
    return tuple(sorted(normalized))
