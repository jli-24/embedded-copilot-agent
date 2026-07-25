from __future__ import annotations

import copy
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import Field, field_serializer, field_validator, model_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel
from embedded_copilot.knowledge.source import KnowledgeSourceType

_URI_METADATA_KEYS = frozenset({"uri", "repository", "owner", "category"})
_SAFE_METADATA_VALUE = re.compile(r"^[^\r\n\x00]{1,512}$")
_SENSITIVE_VALUE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret)\s*[:=])",
    re.IGNORECASE,
)


class SearchStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class SearchReviewAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_MODIFICATION = "REQUEST_MODIFICATION"


class _FrozenUriMetadata(Mapping[str, str]):
    __slots__ = ("_items",)

    def __init__(self, items: Iterator[tuple[str, str]]) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> str:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __deepcopy__(self, memo: dict[int, object]) -> "_FrozenUriMetadata":
        return self


def _validate_uri(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("search URI metadata is unsafe")
    return value


def _validated_uri_metadata(value: object) -> dict[str, str]:
    copied = copy.deepcopy(value)
    if not isinstance(copied, Mapping) or "uri" not in copied:
        raise ValueError("search URI metadata is invalid")
    validated: dict[str, str] = {}
    for raw_key, raw_value in copied.items():
        if not isinstance(raw_key, str):
            raise ValueError("search URI metadata key is invalid")
        key = raw_key.strip().casefold()
        if key not in _URI_METADATA_KEYS or not isinstance(raw_value, str):
            raise ValueError("search URI metadata is invalid")
        item = raw_value.strip()
        if not _SAFE_METADATA_VALUE.fullmatch(item) or _SENSITIVE_VALUE.search(item):
            raise ValueError("search URI metadata is unsafe")
        validated[key] = _validate_uri(item) if key == "uri" else item
    return dict(sorted(validated.items()))


class SearchRequest(IntelligenceContractModel):
    query: str
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return safe_text(value, field="query", max_length=512)


class SearchResult(IntelligenceContractModel):
    result_id: str
    source_id: str
    source_type: KnowledgeSourceType
    title: str
    summary: str
    relevance_score: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    uri_metadata: Mapping[str, str]
    status: SearchStatus = SearchStatus.PENDING

    @field_validator("result_id", "source_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return safe_identifier(value, field=info.field_name)

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: object) -> str:
        return safe_text(value, field="title", max_length=256)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=512)

    @field_validator("relevance_score", mode="before")
    @classmethod
    def validate_relevance_score(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("relevance score is invalid")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("relevance score is invalid")
        return value

    @field_validator("source_type")
    @classmethod
    def validate_source_type(
        cls,
        value: KnowledgeSourceType,
    ) -> KnowledgeSourceType:
        if value not in {KnowledgeSourceType.GITHUB, KnowledgeSourceType.WEB}:
            raise ValueError("search source type is invalid")
        return value

    @field_validator("uri_metadata", mode="before")
    @classmethod
    def validate_uri_metadata(cls, value: object) -> object:
        return _validated_uri_metadata(value)

    @field_validator("uri_metadata", mode="after")
    @classmethod
    def freeze_uri_metadata(
        cls,
        value: Mapping[str, str],
    ) -> Mapping[str, str]:
        return _FrozenUriMetadata(iter(value.items()))

    @field_serializer("uri_metadata")
    def serialize_uri_metadata(self, value: Mapping[str, str]) -> dict[str, str]:
        return dict(value)


class ApprovedSearchCandidate(IntelligenceContractModel):
    source_id: str
    source_type: KnowledgeSourceType
    summary: str
    uri_metadata: Mapping[str, str]

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        return safe_identifier(value, field="source_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", max_length=512)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(
        cls,
        value: KnowledgeSourceType,
    ) -> KnowledgeSourceType:
        if value not in {KnowledgeSourceType.GITHUB, KnowledgeSourceType.WEB}:
            raise ValueError("search source type is invalid")
        return value

    @field_validator("uri_metadata", mode="before")
    @classmethod
    def validate_uri_metadata(cls, value: object) -> object:
        return _validated_uri_metadata(value)

    @field_validator("uri_metadata", mode="after")
    @classmethod
    def freeze_uri_metadata(
        cls,
        value: Mapping[str, str],
    ) -> Mapping[str, str]:
        return _FrozenUriMetadata(iter(value.items()))

    @field_serializer("uri_metadata")
    def serialize_uri_metadata(self, value: Mapping[str, str]) -> dict[str, str]:
        return dict(value)


class SearchHistory(IntelligenceContractModel):
    history_id: str
    request: SearchRequest
    results: tuple[SearchResult, ...] = ()

    @field_validator("history_id", mode="before")
    @classmethod
    def validate_history_id(cls, value: object) -> str:
        return safe_identifier(value, field="history_id")

    @field_validator("request", "results", mode="before")
    @classmethod
    def isolate_nested_state(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("results", mode="before")
    @classmethod
    def normalize_results(cls, value: object) -> object:
        if not isinstance(value, Sequence) or isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return value
        return tuple(value)

    @model_validator(mode="after")
    def validate_result_binding(self) -> "SearchHistory":
        if len(self.results) > self.request.limit:
            raise ValueError("search history exceeds request limit")
        result_ids = [item.result_id.casefold() for item in self.results]
        if len(set(result_ids)) != len(result_ids):
            raise ValueError("search result IDs must be unique")
        return self
