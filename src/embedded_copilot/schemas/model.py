from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator

from embedded_copilot.schemas.result import ContractModel

_MODEL_CONTEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


class ModelTaskType(StrEnum):
    CHAT = "CHAT"
    VISION = "VISION"
    CODE = "CODE"
    REASONING = "REASONING"


class ModelInputType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"


class ModelRequest(ContractModel):
    """Provider-neutral request contract shared with Copilot Workspace."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    task_type: ModelTaskType
    input_type: ModelInputType
    context_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator("context_ids", mode="before")
    @classmethod
    def validate_context_ids(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        copied = copy.deepcopy(value)
        normalized: list[str] = []
        for raw_identifier in copied:
            if not isinstance(raw_identifier, str):
                raise ValueError("context_id must be a string")
            identifier = raw_identifier.strip()
            if not _MODEL_CONTEXT_ID.fullmatch(identifier):
                raise ValueError("context_id is invalid")
            normalized.append(identifier)
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError("context_id must be unique")
        return tuple(normalized)
