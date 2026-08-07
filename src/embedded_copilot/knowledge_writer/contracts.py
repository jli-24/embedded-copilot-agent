from __future__ import annotations

import copy
import re
import unicodedata
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.engineering_knowledge.models import (
    EngineeringGraphSnapshot,
    NodeType,
    validate_graph_snapshot,
)
from embedded_copilot.engineering_memory import (
    ApprovedEngineeringMemory,
    ApprovedMemoryProjection,
    EngineeringMemoryType,
)
from embedded_copilot.engineering_memory.models import (
    MemoryType as LegacyEngineeringMemoryType,
)
from embedded_copilot.memory_automation.contracts import MemoryType

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,255}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key|access[_ -]?token|password|credential|secret)\s*[:=]"
    r"|bearer\s+|sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE
)


class WriterContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class KnowledgeWriteStatus(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    REJECTED = "REJECTED"


def _text(value: object, *, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value).strip()
    if (
        not candidate
        or len(candidate) > maximum
        or "\x00" in candidate
        or "\n" in candidate
        or "\r" in candidate
        or _SENSITIVE.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _id(value: object, *, field: str) -> str:
    candidate = _text(value, field=field, maximum=128)
    if not _ID.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _reference(value: object, *, field: str) -> str:
    candidate = _text(value, field=field, maximum=256)
    if not _REFERENCE.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


class MarkdownArtifact(WriterContract):
    memory_id: str
    memory_type: MemoryType | LegacyEngineeringMemoryType | EngineeringMemoryType
    status: str
    layer: str
    tags: tuple[str, ...]
    title: str
    summary: str
    evidence_references: tuple[str, ...]
    relative_path: str
    candidate_fingerprint: str
    decision: str = ""
    reason: str = ""
    related_links: tuple[str, ...] = ()

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_memory_id(cls, value: object) -> str:
        return _id(value, field="memory_id")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        if value != "APPROVED":
            raise ValueError("artifact must be approved")
        return "APPROVED"

    @field_validator(
        "layer", "title", "summary", "decision", "reason", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("tags", "evidence_references", mode="before")
    @classmethod
    def tuple_only(cls, value: object, info) -> object:
        if not isinstance(value, tuple):
            raise TypeError(f"{info.field_name} must be a tuple")
        return copy.deepcopy(value)

    @field_validator("related_links", mode="before")
    @classmethod
    def tuple_only_related_links(cls, value: object) -> object:
        if not isinstance(value, tuple):
            raise TypeError("related_links must be a tuple")
        return copy.deepcopy(value)

    @field_validator("tags", "evidence_references")
    @classmethod
    def validate_safe_references(
        cls, value: tuple[str, ...], info
    ) -> tuple[str, ...]:
        return tuple(_text(item, field=info.field_name, maximum=256) for item in value)

    @field_validator("related_links")
    @classmethod
    def validate_related_links(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_text(item, field="related_link", maximum=256) for item in value)

    @field_validator("candidate_fingerprint", mode="before")
    @classmethod
    def fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
            raise ValueError("candidate_fingerprint is invalid")
        return value

    @field_validator("relative_path", mode="before")
    @classmethod
    def path(cls, value: object) -> str:
        if not isinstance(value, str) or not value.startswith("docs/knowledge/"):
            raise ValueError("artifact path is invalid")
        if "\\" in value or ".." in value or "\x00" in value:
            raise ValueError("artifact path is invalid")
        return value

    @model_validator(mode="after")
    def validate_type_and_status(self) -> MarkdownArtifact:
        if self.status != "APPROVED":
            raise ValueError("artifact must be approved")
        prefix = (
            "docs/knowledge/99_Memory/"
            if isinstance(self.memory_type, EngineeringMemoryType)
            else "docs/knowledge/"
        )
        expected = f"{prefix}{self.memory_id}-{self.memory_type.value.lower()}.md"
        if self.relative_path != expected:
            raise ValueError("artifact path is not deterministic")
        return self


class KnowledgeWriteResult(WriterContract):
    status: KnowledgeWriteStatus
    memory_id: str
    event_type: str | None = None
    message: str

    @field_validator("memory_id", mode="before")
    @classmethod
    def validate_id(cls, value: object) -> str:
        return _id(value, field="memory_id")

    @field_validator("message", mode="before")
    @classmethod
    def validate_message(cls, value: object) -> str:
        return _text(value, field="message", maximum=256)


class GraphMarkdownArtifact(WriterContract):
    node_id: str
    project_id: str
    node_type: NodeType
    entity_name: str
    summary: str
    source_reference: str
    confidence: float
    verification_status: str
    fingerprint: str
    relative_path: str
    related_links: tuple[str, ...] = ()

    @field_validator("node_id", "project_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _id(value, field=info.field_name)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: object) -> str:
        return _reference(value, field="source_reference")

    @field_validator("entity_name", "summary", mode="before")
    @classmethod
    def validate_text_fields(cls, value: object, info) -> str:
        return _text(value, field=info.field_name)

    @field_validator("verification_status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        if value != "APPROVED":
            raise ValueError("graph artifact must be approved")
        return "APPROVED"

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
            raise ValueError("fingerprint is invalid")
        return value

    @field_validator("related_links", mode="before")
    @classmethod
    def validate_links(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("related_links must be a tuple")
        return copy.deepcopy(value)

    @field_validator("related_links")
    @classmethod
    def validate_link_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_text(item, field="related_link", maximum=256) for item in value)

    @field_validator("relative_path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> str:
        if not isinstance(value, str) or not value.startswith(
            "docs/knowledge/99_KnowledgeGraph/"
        ):
            raise ValueError("graph artifact path is invalid")
        if "\\" in value or ".." in value or "\x00" in value:
            raise ValueError("graph artifact path is invalid")
        return value

    @model_validator(mode="after")
    def validate_deterministic_path(self) -> GraphMarkdownArtifact:
        expected = (
            "docs/knowledge/99_KnowledgeGraph/" + self.node_id + ".md"
        )
        if self.relative_path != expected:
            raise ValueError("graph artifact path is not deterministic")
        return self


class KnowledgeWriterPort(Protocol):
    def write(self, artifact: MarkdownArtifact) -> KnowledgeWriteResult: ...

    def write_approved_memory(
        self, memory: ApprovedEngineeringMemory
    ) -> KnowledgeWriteResult: ...

    def write_approved_projection(
        self, projection: ApprovedMemoryProjection
    ) -> KnowledgeWriteResult: ...

    def write_approved_graph_projection(
        self, snapshot: EngineeringGraphSnapshot
    ) -> tuple[KnowledgeWriteResult, ...]: ...


def artifact_from_approved_graph_snapshot(
    snapshot: EngineeringGraphSnapshot,
) -> tuple[GraphMarkdownArtifact, ...]:
    checked = validate_graph_snapshot(snapshot)
    relations_by_node: dict[str, set[str]] = {
        node.node_id: set() for node in checked.nodes
    }
    for relation in checked.relations:
        relations_by_node[relation.source_node_id].add(relation.target_node_id)
        relations_by_node[relation.target_node_id].add(relation.source_node_id)
    return tuple(
        GraphMarkdownArtifact(
            node_id=node.node_id,
            project_id=node.project_id,
            node_type=node.node_type,
            entity_name=node.entity_name,
            summary=node.summary,
            source_reference=node.source_reference,
            confidence=node.confidence,
            verification_status=node.verification_status,
            fingerprint=node.fingerprint,
            relative_path=(
                "docs/knowledge/99_KnowledgeGraph/" + node.node_id + ".md"
            ),
            related_links=tuple(
                f"[[{target}]]" for target in sorted(relations_by_node[node.node_id])
            ),
        )
        for node in checked.nodes
    )


def artifact_from_approved_projection(
    projection: ApprovedMemoryProjection,
) -> MarkdownArtifact:
    if type(projection) is not ApprovedMemoryProjection:
        raise TypeError("approved memory projection must be typed")
    checked = ApprovedMemoryProjection.model_validate(projection.model_copy(deep=True))
    return MarkdownArtifact(
        memory_id=checked.memory_id,
        memory_type=LegacyEngineeringMemoryType(checked.memory_type),
        status="APPROVED",
        layer="engineering-memory",
        tags=("engineering-memory",),
        title=checked.title,
        summary=checked.summary,
        evidence_references=checked.evidence_references,
        relative_path=(
            f"docs/knowledge/{checked.memory_id}-"
            f"{checked.memory_type.casefold()}.md"
        ),
        candidate_fingerprint=checked.fingerprint,
        decision=checked.summary,
        reason=checked.title,
    )


def artifact_from_approved_memory(
    memory: ApprovedEngineeringMemory,
) -> MarkdownArtifact:
    if type(memory) is not ApprovedEngineeringMemory:
        raise TypeError("approved engineering memory must be typed")
    checked = ApprovedEngineeringMemory.model_validate(memory.model_copy(deep=True))
    return MarkdownArtifact(
        memory_id=checked.memory_id,
        memory_type=checked.memory_type,
        status="APPROVED",
        layer="engineering-memory",
        tags=("engineering-memory", checked.memory_type.value.casefold()),
        title=checked.memory_type.value.title(),
        summary=checked.summary,
        evidence_references=checked.evidence,
        relative_path=(
            f"docs/knowledge/99_Memory/{checked.memory_id}-"
            f"{checked.memory_type.value.casefold()}.md"
        ),
        candidate_fingerprint=checked.fingerprint,
        decision=checked.decision,
        reason=checked.reason,
        related_links=checked.evidence,
    )
