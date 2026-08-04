from __future__ import annotations

import copy
import re
import unicodedata
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ComponentContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def _text(value: object, *, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    text = unicodedata.normalize("NFC", value.strip())
    if (
        not text
        or len(text) > maximum
        or any(char in text for char in ("\x00", "\r", "\n"))
        or re.search(
            r"(?:password|credential|secret|token|api[_ -]?key)\s*[:=]", text, re.I
        )
    ):
        raise ValueError(f"{field} is unsafe")
    return text


def _url(value: object) -> str:
    text = _text(value, field="supplier_link", maximum=512)
    if not re.fullmatch(r"https://[^\s/]+(?:/[^\s]*)?", text, re.IGNORECASE):
        raise ValueError("supplier_link is invalid")
    return text


class ComponentRecommendation(ComponentContract):
    part_number: str
    manufacturer: str
    reason: str
    datasheet_reference: str
    supplier_links: tuple[str, ...] = Field(max_length=16)
    alternatives: tuple[str, ...] = Field(max_length=16)

    @field_validator(
        "part_number", "manufacturer", "reason", "datasheet_reference", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("supplier_links", mode="before")
    @classmethod
    def validate_links(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("supplier_links must be a tuple")
        return tuple(_url(item) for item in value)

    @field_validator("alternatives", mode="before")
    @classmethod
    def validate_alternatives(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("alternatives must be a tuple")
        return tuple(_text(item, field="alternative") for item in value)


@runtime_checkable
class ComponentRecommendationPort(Protocol):
    def get_recommendations(
        self, project_id: str
    ) -> tuple[ComponentRecommendation, ...] | None: ...


def validate_recommendations(value: object) -> tuple[ComponentRecommendation, ...]:
    if type(value) is not tuple:
        raise TypeError("recommendations must be a tuple")
    checked_items: list[ComponentRecommendation] = []
    for item in value:
        if type(item) is not ComponentRecommendation:
            raise TypeError("recommendation is invalid")
        checked_items.append(
            ComponentRecommendation.model_validate(
                copy.deepcopy(item.model_dump(mode="python"))
            )
        )
    checked = tuple(checked_items)
    parts = tuple(item.part_number for item in checked)
    if len(parts) != len(set(parts)):
        raise ValueError("recommendations must be unique")
    return checked


__all__ = [
    "ComponentRecommendation",
    "ComponentRecommendationPort",
    "validate_recommendations",
]
