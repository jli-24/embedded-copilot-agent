from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.datasheet_runtime import DatasheetRequest
from embedded_copilot.engineering_memory import (
    CreateCandidateRequest,
    KnownIssueMemory,
)
from embedded_copilot.knowledge.source import KnowledgeSourceType

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_FACT_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_DATASHEET_REFERENCE = re.compile(
    r"^datasheet:[A-Za-z0-9][A-Za-z0-9._:#-]{0,239}$"
)
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?<![A-Za-z0-9._~-])/[^/\s]+)",
    re.IGNORECASE,
)
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=]|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)


class _KnowledgeContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, maximum: int = 512) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > maximum
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _reference(value: object) -> str:
    if type(value) is not str:
        raise ValueError("reference is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > 512
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _SENSITIVE.search(candidate)
    ):
        raise ValueError("reference is unsafe")
    if _DATASHEET_REFERENCE.fullmatch(candidate):
        return candidate
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
    ):
        raise ValueError("reference is unsafe")
    return candidate


def _fingerprint_payload(value: BaseModel) -> str:
    payload = value.model_dump(mode="json", exclude={"fingerprint"})
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class KnowledgeEntityType(StrEnum):
    COMPONENT = "COMPONENT"
    INTERFACE = "INTERFACE"
    CONSTRAINT = "CONSTRAINT"
    CAPABILITY = "CAPABILITY"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"
    FAILURE_RULE = "FAILURE_RULE"


class KnowledgeRelationshipType(StrEnum):
    SUPPORTS = "supports"
    REQUIRES = "requires"
    CONFLICTS = "conflicts"
    COMPATIBLE_WITH = "compatible_with"
    DERIVED_FROM = "derived_from"


class KnowledgeVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class KnowledgeVerificationMethod(StrEnum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    PUBLISHER_CONSENSUS = "PUBLISHER_CONSENSUS"


class SourceTrustLevel(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    COMMUNITY = "COMMUNITY"


class KnowledgeFailureSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SourceTrustEntry(_KnowledgeContract):
    source_type: KnowledgeSourceType
    publisher: str
    trust_level: SourceTrustLevel

    @field_validator("publisher", mode="before")
    @classmethod
    def validate_publisher(cls, value: object) -> str:
        return _safe_text(value, field="publisher", maximum=160)


class SourceTrustCatalog(_KnowledgeContract):
    entries: tuple[SourceTrustEntry, ...]

    @field_validator("entries", mode="before")
    @classmethod
    def validate_entries_tuple(cls, value: object) -> object:
        return _tuple(value, field="entries")

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> SourceTrustCatalog:
        keys = tuple(
            (entry.source_type, entry.publisher.casefold()) for entry in self.entries
        )
        if len(keys) != len(set(keys)):
            raise ValueError("source trust bindings must be unique")
        return self

    def trust_for(
        self,
        source_type: KnowledgeSourceType,
        publisher: str,
    ) -> SourceTrustLevel | None:
        key = publisher.casefold()
        return next(
            (
                entry.trust_level
                for entry in self.entries
                if entry.source_type is source_type
                and entry.publisher.casefold() == key
            ),
            None,
        )


class KnowledgeRelationshipCandidate(_KnowledgeContract):
    relationship_type: KnowledgeRelationshipType
    target_entity_id: str

    @field_validator("target_entity_id", mode="before")
    @classmethod
    def validate_target_entity_id(cls, value: object) -> str:
        return _identifier(value, field="target_entity_id")


class FailureRuleCandidate(_KnowledgeContract):
    issue_key: str
    title: str
    severity: KnowledgeFailureSeverity
    description_summary: str
    mitigation_summary: str

    @field_validator("issue_key", mode="before")
    @classmethod
    def validate_issue_key(cls, value: object) -> str:
        return _identifier(value, field="issue_key")

    @field_validator(
        "title", "description_summary", "mitigation_summary", mode="before"
    )
    @classmethod
    def validate_summary(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)


class EngineeringKnowledgeRequest(_KnowledgeContract):
    request_id: str
    query_summary: str

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, value: object) -> str:
        return _identifier(value, field="request_id")

    @field_validator("query_summary", mode="before")
    @classmethod
    def validate_query_summary(cls, value: object) -> str:
        return _safe_text(value, field="query_summary")


class DatasheetKnowledgeRequest(_KnowledgeContract):
    request_id: str
    datasheet_request: DatasheetRequest
    publisher: str
    reference: str
    observed_at: datetime

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, value: object) -> str:
        return _identifier(value, field="request_id")

    @field_validator("publisher", mode="before")
    @classmethod
    def validate_publisher(cls, value: object) -> str:
        return _safe_text(value, field="publisher", maximum=160)

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _reference(value)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class KnowledgeSourceCandidate(_KnowledgeContract):
    evidence_id: str
    entity_type: KnowledgeEntityType
    fact_key: str
    canonical_value: str
    summary: str
    source_type: KnowledgeSourceType
    publisher: str
    reference: str
    observed_at: datetime
    provider_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        allow_inf_nan=False,
    )
    relationships: tuple[KnowledgeRelationshipCandidate, ...] = ()
    failure_rule: FailureRuleCandidate | None = None

    @field_validator("evidence_id", mode="before")
    @classmethod
    def validate_evidence_id(cls, value: object) -> str:
        return _identifier(value, field="evidence_id")

    @field_validator("fact_key", mode="before")
    @classmethod
    def validate_fact_key(cls, value: object) -> str:
        candidate = _identifier(value, field="fact_key")
        if _FACT_KEY.fullmatch(candidate) is None:
            raise ValueError("fact_key is invalid")
        return candidate

    @field_validator("canonical_value", "summary", mode="before")
    @classmethod
    def validate_safe_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("publisher", mode="before")
    @classmethod
    def validate_publisher(cls, value: object) -> str:
        return _safe_text(value, field="publisher", maximum=160)

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _reference(value)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("provider_confidence", mode="before")
    @classmethod
    def validate_provider_confidence(cls, value: object) -> object:
        if value is not None and (type(value) is not float or not math.isfinite(value)):
            raise ValueError("provider confidence is invalid")
        return value

    @field_validator("relationships", mode="before")
    @classmethod
    def validate_relationship_tuple(cls, value: object) -> object:
        return _tuple(value, field="relationships")

    @model_validator(mode="after")
    def validate_failure_rule_binding(self) -> KnowledgeSourceCandidate:
        if (self.entity_type is KnowledgeEntityType.FAILURE_RULE) != (
            self.failure_rule is not None
        ):
            raise ValueError("failure rule binding is invalid")
        keys = tuple(
            (item.relationship_type, item.target_entity_id)
            for item in self.relationships
        )
        if len(keys) != len(set(keys)):
            raise ValueError("relationships must be unique")
        return self


class KnowledgeProvenance(_KnowledgeContract):
    source_type: KnowledgeSourceType
    publisher: str
    reference: str
    verification_method: KnowledgeVerificationMethod
    verified_at: datetime
    confidence: Literal[1.0] = 1.0

    @field_validator("publisher", mode="before")
    @classmethod
    def validate_publisher(cls, value: object) -> str:
        return _safe_text(value, field="publisher", maximum=160)

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _reference(value)

    @field_validator("verified_at")
    @classmethod
    def validate_verified_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float or value != 1.0:
            raise ValueError("verified confidence must be 1.0")
        return value


class VerifiedKnowledgeEvidence(_KnowledgeContract):
    evidence_id: str
    entity_type: KnowledgeEntityType
    fact_key: str
    canonical_value: str
    summary: str
    verification_status: Literal[KnowledgeVerificationStatus.VERIFIED] = (
        KnowledgeVerificationStatus.VERIFIED
    )
    confidence: Literal[1.0] = 1.0
    provenance: tuple[KnowledgeProvenance, ...] = Field(min_length=1)
    relationships: tuple[KnowledgeRelationshipCandidate, ...] = ()
    failure_rule: FailureRuleCandidate | None = None

    @field_validator("evidence_id", mode="before")
    @classmethod
    def validate_evidence_id(cls, value: object) -> str:
        return _identifier(value, field="evidence_id")

    @field_validator("fact_key", mode="before")
    @classmethod
    def validate_fact_key(cls, value: object) -> str:
        candidate = _identifier(value, field="fact_key")
        if _FACT_KEY.fullmatch(candidate) is None:
            raise ValueError("fact_key is invalid")
        return candidate

    @field_validator("canonical_value", "summary", mode="before")
    @classmethod
    def validate_safe_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float or value != 1.0:
            raise ValueError("verified confidence must be 1.0")
        return value

    @field_validator("provenance", "relationships", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_bindings(self) -> VerifiedKnowledgeEvidence:
        if (self.entity_type is KnowledgeEntityType.FAILURE_RULE) != (
            self.failure_rule is not None
        ):
            raise ValueError("failure rule binding is invalid")
        publisher_keys = tuple(
            item.publisher.casefold() for item in self.provenance
        )
        if len(publisher_keys) != len(set(publisher_keys)):
            raise ValueError("provenance publishers must be unique")
        return self


class KnowledgeVerificationOutcome(_KnowledgeContract):
    verified_evidence: tuple[VerifiedKnowledgeEvidence, ...] = ()
    rejected_count: int = Field(default=0, ge=0)
    review_required_count: int = Field(default=0, ge=0)

    @field_validator("verified_evidence", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="verified_evidence")


class KnowledgeProgressTrace(_KnowledgeContract):
    sequence: int = Field(ge=1)
    stage: Literal["source", "datasheet", "verification", "projection"]
    status: Literal["started", "completed", "rejected"]
    count: int = Field(ge=0)
    source_type: KnowledgeSourceType


class KnowledgeIntelligenceResult(_KnowledgeContract):
    verified_evidence: tuple[VerifiedKnowledgeEvidence, ...] = ()
    rejected_count: int = Field(default=0, ge=0)
    review_required_count: int = Field(default=0, ge=0)
    graph_evidence_projection: KnowledgeGraphEvidenceProjection | None = None
    trace: tuple[KnowledgeProgressTrace, ...] = ()

    @field_validator("verified_evidence", "trace", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)


class KnowledgeGraphEntity(_KnowledgeContract):
    entity_id: str
    entity_type: KnowledgeEntityType
    canonical_value: str
    summary: str
    evidence: tuple[VerifiedKnowledgeEvidence, ...] = Field(min_length=1)

    @field_validator("entity_id", mode="before")
    @classmethod
    def validate_entity_id(cls, value: object) -> str:
        return _identifier(value, field="entity_id")

    @field_validator("canonical_value", "summary", mode="before")
    @classmethod
    def validate_safe_text(cls, value: object, info) -> str:
        return _safe_text(value, field=info.field_name)

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence")


class KnowledgeGraphRelationship(_KnowledgeContract):
    relationship_id: str
    source_entity_id: str
    relationship_type: KnowledgeRelationshipType
    target_entity_id: str
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "relationship_id", "source_entity_id", "target_entity_id", mode="before"
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def validate_evidence_ids_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence_ids")


class FrozenKnowledgeGraphSnapshot(_KnowledgeContract):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str
    entities: tuple[KnowledgeGraphEntity, ...]
    relationships: tuple[KnowledgeGraphRelationship, ...]
    fingerprint: str

    @field_validator("snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        return _identifier(value, field="snapshot_id")

    @field_validator("entities", "relationships", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> FrozenKnowledgeGraphSnapshot:
        if self.fingerprint != _fingerprint_payload(self):
            raise ValueError("knowledge graph fingerprint does not match content")
        return self


class KnowledgeGraphProjectionRequest(_KnowledgeContract):
    snapshot_id: str
    evidence: tuple[VerifiedKnowledgeEvidence, ...]

    @field_validator("snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        return _identifier(value, field="snapshot_id")

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence")


class KnowledgeGraphQuery(_KnowledgeContract):
    query_id: str
    snapshot: FrozenKnowledgeGraphSnapshot
    entity_ids: tuple[str, ...] = ()
    relationship_types: tuple[KnowledgeRelationshipType, ...] = ()

    @field_validator("query_id", mode="before")
    @classmethod
    def validate_query_id(cls, value: object) -> str:
        return _identifier(value, field="query_id")

    @field_validator("entity_ids", "relationship_types", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)


class KnowledgeGraphEvidenceProjection(_KnowledgeContract):
    query_id: str
    snapshot_fingerprint: str
    evidence: tuple[VerifiedKnowledgeEvidence, ...]
    relationships: tuple[KnowledgeGraphRelationship, ...]

    @field_validator("query_id", mode="before")
    @classmethod
    def validate_query_id(cls, value: object) -> str:
        return _identifier(value, field="query_id")

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_snapshot_fingerprint(cls, value: object) -> str:
        if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
            raise ValueError("snapshot fingerprint is invalid")
        return value

    @field_validator("evidence", "relationships", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)


class MemoryBridgeRequest(_KnowledgeContract):
    request_id: str
    operation_id: str
    project_id: str
    memory_id: str
    record_id: str
    expected_revision: int = Field(ge=0)
    caller: str
    requested_at: datetime
    evidence: VerifiedKnowledgeEvidence

    @field_validator(
        "request_id",
        "operation_id",
        "project_id",
        "memory_id",
        "record_id",
        "caller",
        mode="before",
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value)


class MemoryBridgeProjection(_KnowledgeContract):
    evidence_id: str
    candidate: KnownIssueMemory
    create_request: CreateCandidateRequest

    @field_validator("evidence_id", mode="before")
    @classmethod
    def validate_evidence_id(cls, value: object) -> str:
        return _identifier(value, field="evidence_id")


def knowledge_graph_fingerprint(
    snapshot: FrozenKnowledgeGraphSnapshot,
) -> str:
    return _fingerprint_payload(snapshot)


KnowledgeIntelligenceResult.model_rebuild()
