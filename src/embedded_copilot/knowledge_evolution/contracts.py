from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.engineering_knowledge.models import EngineeringGraphSnapshot
from embedded_copilot.engineering_memory import ApprovedEngineeringMemory

from .models import (
    canonical_fingerprint,
    fingerprint,
    identifier,
    safe_text,
    tuple_only,
)


class KnowledgeContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class KnowledgeEntityType(StrEnum):
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    BUILD = "BUILD"
    VALIDATION = "VALIDATION"
    OPTIMIZATION = "OPTIMIZATION"
    DECISION = "DECISION"
    CONSTRAINT = "CONSTRAINT"


class KnowledgeConfidence(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class KnowledgeRelationType(StrEnum):
    USED_WITH = "USED_WITH"
    VALIDATED_BY = "VALIDATED_BY"
    OPTIMIZED_BY = "OPTIMIZED_BY"
    FAILED_BY = "FAILED_BY"
    REPLACED_BY = "REPLACED_BY"


class EngineeringKnowledgeNode(KnowledgeContract):
    node_id: str
    project_id: str
    entity_type: KnowledgeEntityType
    reference: str
    attributes: tuple[str, ...] = Field(max_length=128)
    confidence: KnowledgeConfidence
    fingerprint: str

    @field_validator("node_id", "project_id", "reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("attributes", mode="before")
    @classmethod
    def validate_attributes(cls, value: object) -> object:
        return tuple_only(value, field="attributes")

    @field_validator("attributes")
    @classmethod
    def validate_attribute_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(safe_text(item, field="attribute") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("attributes must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringKnowledgeNode:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("knowledge node fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringKnowledgeNode:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringKnowledgeRelation(KnowledgeContract):
    relation_id: str
    source_id: str
    target_id: str
    relation_type: KnowledgeRelationType
    evidence_reference: str
    confidence: KnowledgeConfidence
    fingerprint: str

    @field_validator(
        "relation_id", "source_id", "target_id", "evidence_reference", mode="before"
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringKnowledgeRelation:
        if (
            self.confidence is KnowledgeConfidence.UNVERIFIED
            and self.evidence_reference.startswith("verified:")
        ):
            raise ValueError("unverified relation cannot use verified evidence")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("knowledge relation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringKnowledgeRelation:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class EngineeringKnowledgeSnapshot(KnowledgeContract):
    project_id: str
    nodes: tuple[EngineeringKnowledgeNode, ...] = Field(max_length=256)
    relations: tuple[EngineeringKnowledgeRelation, ...] = Field(max_length=256)
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("nodes", "relations", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> EngineeringKnowledgeSnapshot:
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("knowledge node ids must be unique")
        if any(node.project_id != self.project_id for node in self.nodes):
            raise ValueError("knowledge node project binding mismatch")
        relation_ids = tuple(relation.relation_id for relation in self.relations)
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("knowledge relation ids must be unique")
        node_set = set(node_ids)
        if any(
            relation.source_id not in node_set or relation.target_id not in node_set
            for relation in self.relations
        ):
            raise ValueError("knowledge relation references unknown node")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("knowledge snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> EngineeringKnowledgeSnapshot:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class KnowledgeQueryRequest(KnowledgeContract):
    project_id: str
    requirement_reference: str
    context_fingerprint: str

    @field_validator("project_id", "requirement_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context_fp(cls, value: object) -> str:
        return fingerprint(value, field="context_fingerprint")


class KnowledgeSuggestion(KnowledgeContract):
    recommendation_id: str
    project_id: str
    matched_reference: str
    reason: str
    evidence_reference: str
    confidence: KnowledgeConfidence
    risk: str
    fingerprint: str

    @field_validator(
        "recommendation_id",
        "project_id",
        "matched_reference",
        "evidence_reference",
        mode="before",
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("reason", "risk", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> KnowledgeSuggestion:
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("knowledge recommendation fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> KnowledgeSuggestion:
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class EngineeringMemoryProjectionPort(Protocol):
    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None: ...


@runtime_checkable
class ApprovedEngineeringMemoryProjectionPort(Protocol):
    def list_approved(
        self, project_id: str
    ) -> tuple[ApprovedEngineeringMemory, ...]: ...


@runtime_checkable
class EngineeringKnowledgeGraphProjectionPort(Protocol):
    """Read-only graph snapshots supplied to Knowledge Evolution."""

    def project(self, project_id: str) -> EngineeringGraphSnapshot | None: ...


KnowledgeEvolutionPort = EngineeringMemoryProjectionPort


@runtime_checkable
class KnowledgeRetrievalPort(Protocol):
    def query(
        self, request: KnowledgeQueryRequest
    ) -> tuple[KnowledgeSuggestion, ...]: ...


KnowledgeRecommendation = KnowledgeSuggestion


def validate_snapshot(value: object) -> EngineeringKnowledgeSnapshot:
    if type(value) is not EngineeringKnowledgeSnapshot:
        raise TypeError("knowledge snapshot is invalid")
    return EngineeringKnowledgeSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_recommendations(value: object) -> tuple[KnowledgeSuggestion, ...]:
    if type(value) is not tuple:
        raise TypeError("recommendations must be a tuple")
    checked = tuple(
        KnowledgeSuggestion.model_validate(
            copy.deepcopy(item.model_dump(mode="python"))
        )
        if type(item) is KnowledgeSuggestion
        else (_ for _ in ()).throw(TypeError("recommendation is invalid"))
        for item in value
    )
    if len({item.recommendation_id for item in checked}) != len(checked):
        raise ValueError("recommendation ids must be unique")
    return checked


__all__ = [
    "ApprovedEngineeringMemoryProjectionPort",
    "EngineeringKnowledgeGraphProjectionPort",
    "EngineeringKnowledgeNode",
    "EngineeringKnowledgeRelation",
    "EngineeringKnowledgeSnapshot",
    "EngineeringMemoryProjectionPort",
    "KnowledgeConfidence",
    "KnowledgeContract",
    "KnowledgeEntityType",
    "KnowledgeEvolutionPort",
    "KnowledgeQueryRequest",
    "KnowledgeRecommendation",
    "KnowledgeRelationType",
    "KnowledgeRetrievalPort",
    "KnowledgeSuggestion",
    "validate_recommendations",
    "validate_snapshot",
]
