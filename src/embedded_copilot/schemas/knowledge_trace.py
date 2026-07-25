from __future__ import annotations

import copy
import re
from collections.abc import Sequence
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.schemas.result import ContractModel

_TRACE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_UNSAFE_QUERY = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|api[_ -]?key\s*[:=]"
    r"|access[_ -]?token\s*[:=]|bearer\s+|password\s*[:=])",
    re.IGNORECASE,
)


class KnowledgeTraceAction(StrEnum):
    VIEWED = "VIEWED"
    USED = "USED"
    SAVED = "SAVED"


class KnowledgeTrace(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    query: str
    source_ids: tuple[str, ...] = ()
    result_count: int = Field(ge=0)
    action: KnowledgeTraceAction

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("query must be a string")
        candidate = value.strip()
        if (
            not candidate
            or len(candidate) > 512
            or any(char in candidate for char in ("\r", "\n", "\x00"))
            or _UNSAFE_QUERY.search(candidate)
        ):
            raise ValueError("query is unsafe")
        return candidate

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_source_ids(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        identifiers: list[str] = []
        for raw_identifier in copy.deepcopy(value):
            if not isinstance(raw_identifier, str):
                raise ValueError("source_id must be a string")
            identifier = raw_identifier.strip()
            if not _TRACE_IDENTIFIER.fullmatch(identifier):
                raise ValueError("source_id is invalid")
            identifiers.append(identifier)
        if len({item.casefold() for item in identifiers}) != len(identifiers):
            raise ValueError("source_id must be unique")
        return tuple(identifiers)

    @model_validator(mode="after")
    def validate_result_binding(self) -> "KnowledgeTrace":
        if bool(self.source_ids) != bool(self.result_count):
            raise ValueError(
                "result count and source IDs must both be empty or populated"
            )
        if self.result_count < len(self.source_ids):
            raise ValueError("result count cannot be lower than unique source count")
        return self
