from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .policy import (
    ContextCategory,
    ContextSourceType,
    ContextVerificationStatus,
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#/-]{0,127}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#/-]{0,255}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_UNSAFE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|https?://|\x00|\r|\n|"
    r"credential|password|secret|token|provider|runtime|prompt|cot|"
    r"stdout|stderr|raw\s+log)",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,63}")


class ContextContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def _text(value: object, *, field: str, maximum: int = 2048) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    checked = unicodedata.normalize("NFC", value).strip()
    if not checked or len(checked) > maximum or _UNSAFE.search(checked):
        raise ValueError(f"{field} is unsafe")
    return checked


def identifier(value: object, *, field: str) -> str:
    checked = _text(value, field=field, maximum=128)
    if not _IDENTIFIER.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


def reference(value: object, *, field: str) -> str:
    checked = _text(value, field=field, maximum=256)
    if not _REFERENCE.fullmatch(checked):
        raise ValueError(f"{field} is invalid")
    return checked


def tuple_only(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise TypeError(f"{field} must be a tuple")
    return copy.deepcopy(value)


def fingerprint(value: object, *, field: str = "fingerprint") -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


def canonical_fingerprint(
    value: BaseModel, *, exclude: set[str] | frozenset[str] = frozenset()
) -> str:
    payload = value.model_dump(mode="json", exclude=exclude)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _confidence(value: object) -> float:
    if type(value) is not float or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("confidence is invalid")
    return value


def _verified_status(value: object, *, field: str = "verification_status") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    checked = value.strip().upper()
    allowed = {
        ContextVerificationStatus.APPROVED.value,
        ContextVerificationStatus.VERIFIED.value,
        ContextVerificationStatus.PROJECTED.value,
        ContextVerificationStatus.SOURCE_METADATA.value,
    }
    if checked not in allowed:
        raise ValueError(f"{field} is not usable")
    return checked


def _with_fingerprint(cls, material: dict[str, object]) -> object:
    provisional = cls.model_construct(
        **{**material, "fingerprint": "sha256:" + "0" * 64}
    )
    material["fingerprint"] = canonical_fingerprint(
        provisional, exclude={"fingerprint"}
    )
    return cls.model_validate(material)


class ApprovedMemoryProjection(ContextContract):
    memory_id: str
    project_id: str
    memory_type: str
    summary: str
    decision: str
    reason: str
    source_reference: str
    confidence: float
    status: Literal["APPROVED"] = "APPROVED"
    fingerprint: str

    @field_validator("memory_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("memory_type", mode="before")
    @classmethod
    def validate_memory_type(cls, value: object) -> str:
        return identifier(value, field="memory_type")

    @field_validator("summary", "decision", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: object) -> str:
        return reference(value, field="source_reference")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> ApprovedMemoryProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("approved memory projection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> ApprovedMemoryProjection:
        material = dict(values)
        material["memory_id"] = identifier(material["memory_id"], field="memory_id")
        material["project_id"] = identifier(
            material["project_id"], field="project_id"
        )
        material["memory_type"] = identifier(
            material["memory_type"], field="memory_type"
        )
        for field in ("summary", "decision", "reason"):
            material[field] = _text(material[field], field=field)
        material["source_reference"] = reference(
            material["source_reference"], field="source_reference"
        )
        material["confidence"] = _confidence(material["confidence"])
        material.setdefault("status", "APPROVED")
        if material["status"] != "APPROVED":
            raise ValueError("status is invalid")
        return _with_fingerprint(cls, material)


class VerifiedKnowledgeProjection(ContextContract):
    source_id: str
    project_id: str
    entity_name: str
    summary: str
    category: ContextCategory
    source_reference: str
    confidence: float
    verification_status: Literal["VERIFIED", "PROJECTED"]
    source_fingerprint: str
    fingerprint: str

    @field_validator("source_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("entity_name", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return reference(value, field="source_reference")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("source_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def verify(self) -> VerifiedKnowledgeProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("knowledge projection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> VerifiedKnowledgeProjection:
        material = dict(values)
        for field in ("source_id", "project_id"):
            material[field] = identifier(material[field], field=field)
        for field in ("entity_name", "summary"):
            material[field] = _text(material[field], field=field)
        material["category"] = ContextCategory(material["category"])
        material["source_reference"] = reference(
            material["source_reference"], field="source_reference"
        )
        material["confidence"] = _confidence(material["confidence"])
        material["verification_status"] = _verified_status(
            material["verification_status"]
        )
        if material["verification_status"] not in {"VERIFIED", "PROJECTED"}:
            raise ValueError("verification_status is invalid")
        for field in ("source_fingerprint",):
            material[field] = fingerprint(material[field], field=field)
        return _with_fingerprint(cls, material)


class DatasheetMetadataProjection(ContextContract):
    source_id: str
    project_id: str
    component: str
    property: str
    source_reference: str
    confidence: float
    verification_status: Literal["SOURCE_METADATA"] = "SOURCE_METADATA"
    source_fingerprint: str
    fingerprint: str

    @field_validator("source_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("component", "property", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return reference(value, field="source_reference")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("source_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def verify(self) -> DatasheetMetadataProjection:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("datasheet projection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> DatasheetMetadataProjection:
        material = dict(values)
        for field in ("source_id", "project_id"):
            material[field] = identifier(material[field], field=field)
        for field in ("component", "property"):
            material[field] = _text(material[field], field=field)
        material["source_reference"] = reference(
            material["source_reference"], field="source_reference"
        )
        material["confidence"] = _confidence(material["confidence"])
        material.setdefault("verification_status", "SOURCE_METADATA")
        if material["verification_status"] != "SOURCE_METADATA":
            raise ValueError("verification_status is invalid")
        material["source_fingerprint"] = fingerprint(
            material["source_fingerprint"], field="source_fingerprint"
        )
        return _with_fingerprint(cls, material)


class ContextSourceReference(ContextContract):
    source_type: ContextSourceType
    source_id: str
    source_reference: str
    source_fingerprint: str
    verification_status: str
    confidence: float
    fingerprint: str

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        return identifier(value, field="source_id")

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return reference(value, field="source_reference")

    @field_validator("source_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @field_validator("verification_status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        return _verified_status(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @model_validator(mode="after")
    def verify(self) -> ContextSourceReference:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("source reference fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> ContextSourceReference:
        material = dict(values)
        material["source_id"] = identifier(material["source_id"], field="source_id")
        material["source_reference"] = reference(
            material["source_reference"], field="source_reference"
        )
        material["source_fingerprint"] = fingerprint(
            material["source_fingerprint"], field="source_fingerprint"
        )
        material["verification_status"] = _verified_status(
            material["verification_status"]
        )
        material["confidence"] = _confidence(material["confidence"])
        return _with_fingerprint(cls, material)


class EngineeringContextItem(ContextContract):
    item_id: str
    project_id: str
    category: ContextCategory
    entity_name: str
    summary: str
    source_references: tuple[ContextSourceReference, ...]
    confidence: float
    verification_status: str
    fingerprint: str

    @field_validator("item_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("entity_name", "summary", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("source_references", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return tuple_only(value, field="source_references")

    @field_validator("verification_status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        return _verified_status(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringContextItem:
        if not self.source_references:
            raise ValueError("context item provenance is required")
        source_ids = tuple(source.source_id for source in self.source_references)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("context item provenance must be unique")
        if any(
            source.source_reference == "" for source in self.source_references
        ):
            raise ValueError("context item provenance is invalid")
        if any(source.source_fingerprint == "" for source in self.source_references):
            raise ValueError("context item provenance fingerprint is required")
        if any(source.source_id == "" for source in self.source_references):
            raise ValueError("context item provenance id is required")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("context item fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringContextItem:
        material = dict(values)
        material["item_id"] = identifier(material["item_id"], field="item_id")
        material["project_id"] = identifier(
            material["project_id"], field="project_id"
        )
        material["category"] = ContextCategory(material["category"])
        material["entity_name"] = _text(material["entity_name"], field="entity_name")
        material["summary"] = _text(material["summary"], field="summary")
        source_values = tuple_only(
            material["source_references"], field="source_references"
        )
        material["source_references"] = tuple(
            ContextSourceReference.model_validate(copy.deepcopy(value))
            for value in source_values
        )
        material["confidence"] = _confidence(material["confidence"])
        material["verification_status"] = _verified_status(
            material["verification_status"]
        )
        return _with_fingerprint(cls, material)

    @property
    def provenance(self) -> tuple[ContextSourceReference, ...]:
        return self.source_references

    @property
    def sources(self) -> tuple[ContextSourceReference, ...]:
        return self.source_references

    @property
    def source_reference(self) -> str:
        return self.source_references[0].source_reference


class EngineeringContextQuery(ContextContract):
    project_id: str
    query: str
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return _text(value, field="query", maximum=512)


def _empty_fingerprint(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


class EngineeringContextSnapshot(ContextContract):
    project_id: str
    query: str
    requirements: tuple[EngineeringContextItem, ...]
    decisions: tuple[EngineeringContextItem, ...]
    constraints: tuple[EngineeringContextItem, ...]
    historical_problems: tuple[EngineeringContextItem, ...]
    solutions: tuple[EngineeringContextItem, ...]
    components: tuple[EngineeringContextItem, ...]
    interfaces: tuple[EngineeringContextItem, ...]
    sources: tuple[ContextSourceReference, ...]
    confidence: float
    verification_status: str
    graph_fingerprint: str
    memory_fingerprint: str
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> str:
        return _text(value, field="query", maximum=512)

    @field_validator(
        "requirements",
        "decisions",
        "constraints",
        "historical_problems",
        "solutions",
        "components",
        "interfaces",
        "sources",
        mode="before",
    )
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _confidence(value)

    @field_validator("verification_status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        return _verified_status(value)

    @field_validator(
        "graph_fingerprint", "memory_fingerprint", "fingerprint", mode="before"
    )
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def verify(self) -> EngineeringContextSnapshot:
        items = (
            *self.requirements,
            *self.decisions,
            *self.constraints,
            *self.historical_problems,
            *self.solutions,
            *self.components,
            *self.interfaces,
        )
        if any(item.project_id != self.project_id for item in items):
            raise ValueError("context item project binding mismatch")
        if any(
            source.source_id == "" or source.source_reference == ""
            for source in self.sources
        ):
            raise ValueError("context source provenance is invalid")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("context snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringContextSnapshot:
        material = dict(values)
        material["project_id"] = identifier(
            material["project_id"], field="project_id"
        )
        material["query"] = _text(material["query"], field="query", maximum=512)
        for field in (
            "requirements",
            "decisions",
            "constraints",
            "historical_problems",
            "solutions",
            "components",
            "interfaces",
        ):
            material[field] = tuple(
                EngineeringContextItem.model_validate(copy.deepcopy(value))
                for value in tuple_only(material[field], field=field)
            )
        material["sources"] = tuple(
            ContextSourceReference.model_validate(copy.deepcopy(value))
            for value in tuple_only(material["sources"], field="sources")
        )
        material["confidence"] = _confidence(material["confidence"])
        material["verification_status"] = _verified_status(
            material["verification_status"]
        )
        for field in ("graph_fingerprint", "memory_fingerprint"):
            material[field] = fingerprint(material[field], field=field)
        return _with_fingerprint(cls, material)


def validate_graph(value: object) -> Any:
    if type(value).__name__ != "EngineeringGraphSnapshot":
        raise TypeError("engineering graph snapshot is invalid")
    validator = getattr(type(value), "model_validate", None)
    dumper = getattr(value, "model_dump", None)
    if not callable(validator) or not callable(dumper):
        raise TypeError("engineering graph snapshot is invalid")
    checked = validator(copy.deepcopy(dumper(mode="python")))
    if type(checked).__name__ != "EngineeringGraphSnapshot":
        raise TypeError("engineering graph snapshot is invalid")
    return checked


def tokens(value: str) -> frozenset[str]:
    return frozenset(item.casefold() for item in _TOKEN.findall(value))


__all__ = (
    "ApprovedMemoryProjection",
    "ContextContract",
    "ContextSourceReference",
    "DatasheetMetadataProjection",
    "EngineeringContextItem",
    "EngineeringContextQuery",
    "EngineeringContextSnapshot",
    "VerifiedKnowledgeProjection",
    "canonical_fingerprint",
    "fingerprint",
    "identifier",
    "reference",
    "tokens",
    "tuple_only",
    "validate_graph",
)
