from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.verification_agent import VerificationSubjectType

from .models import (
    MemorySnapshotRecord,
    MemorySourceType,
    MemoryStatus,
    MemoryType,
    _fingerprint,
    _identifier,
    _safe_reference,
)


class _MemoryRetrievalContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class MemoryDomain(StrEnum):
    FIRMWARE = "FIRMWARE"
    HARDWARE = "HARDWARE"
    PCB = "PCB"
    DEBUG = "DEBUG"
    GENERAL = "GENERAL"


class MemoryTrustBasis(StrEnum):
    VERIFICATION = "VERIFICATION"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _integer(value: object, *, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{field} is invalid")
    return value


def _finite_float(value: object, *, field: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError(f"{field} is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} is invalid")  # noqa: TRY004
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


class MemoryUsageSignal(_MemoryRetrievalContract):
    record_id: str
    usage_count: int = Field(ge=0)

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @field_validator("usage_count", mode="before")
    @classmethod
    def validate_usage_count(cls, value: object) -> int:
        return _integer(
            value,
            field="usage_count",
            minimum=0,
            maximum=2**63 - 1,
        )


class MemoryRetrievalBinding(_MemoryRetrievalContract):
    request_id: str
    project_id: str
    memory_id: str
    caller: str
    requested_at: datetime
    usage_signals: tuple[MemoryUsageSignal, ...] = ()
    limit: int = Field(default=8, ge=1, le=50)

    @field_validator("request_id", "project_id", "memory_id", "caller", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("requested_at", mode="before")
    @classmethod
    def validate_requested_at(cls, value: object) -> datetime:
        return _utc(value, field="requested_at")

    @field_validator("usage_signals", mode="before")
    @classmethod
    def validate_usage_signals_tuple(cls, value: object) -> object:
        return _tuple(value, field="usage_signals")

    @field_validator("usage_signals")
    @classmethod
    def sort_usage_signals(
        cls,
        value: tuple[MemoryUsageSignal, ...],
    ) -> tuple[MemoryUsageSignal, ...]:
        record_ids = tuple(item.record_id for item in value)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("usage signal record IDs must be unique")
        return tuple(sorted(value, key=lambda item: item.record_id))

    @field_validator("limit", mode="before")
    @classmethod
    def validate_limit(cls, value: object) -> int:
        return _integer(value, field="limit", minimum=1, maximum=50)


class MemoryRetrievalRequest(MemoryRetrievalBinding):
    domains: tuple[MemoryDomain, ...]

    @field_validator("domains", mode="before")
    @classmethod
    def validate_domains_tuple(cls, value: object) -> object:
        return _tuple(value, field="domains")

    @field_validator("domains")
    @classmethod
    def sort_domains(
        cls,
        value: tuple[MemoryDomain, ...],
    ) -> tuple[MemoryDomain, ...]:
        if not value:
            raise ValueError("domains must be non-empty")
        if len(value) != len(set(value)):
            raise ValueError("domains must be unique")
        return tuple(sorted(value, key=lambda item: item.value))


class MemoryRankingBreakdown(_MemoryRetrievalContract):
    verification_millis: int = Field(ge=0, le=1000)
    domain_millis: int = Field(ge=0, le=1000)
    usage_millis: int = Field(ge=0, le=1000)
    recency_millis: int = Field(ge=0, le=1000)
    total_millis: int = Field(ge=0, le=1000)
    relevance_score: float = Field(ge=0.0, le=1.0)

    @field_validator(
        "verification_millis",
        "domain_millis",
        "usage_millis",
        "recency_millis",
        "total_millis",
        mode="before",
    )
    @classmethod
    def validate_millis(cls, value: object, info) -> int:
        return _integer(value, field=info.field_name, minimum=0, maximum=1000)

    @field_validator("relevance_score", mode="before")
    @classmethod
    def validate_relevance_score(cls, value: object) -> float:
        score = _finite_float(value, field="relevance_score")
        if not 0.0 <= score <= 1.0:
            raise ValueError("relevance_score is invalid")
        return score

    @model_validator(mode="after")
    def validate_score_consistency(self) -> MemoryRankingBreakdown:
        expected_total = (
            4 * self.verification_millis
            + 3 * self.domain_millis
            + 2 * self.usage_millis
            + self.recency_millis
        ) // 10
        if (
            self.total_millis != expected_total
            or self.relevance_score != self.total_millis / 1000
        ):
            raise ValueError("ranking score is not consistent")
        return self


class MemoryContextEvidence(_MemoryRetrievalContract):
    record_id: str
    memory_type: MemoryType
    logical_key: str
    trust_basis: MemoryTrustBasis
    verification_subject: VerificationSubjectType | None
    verification_confidence: float | None
    provenance_source_type: MemorySourceType
    provenance_reference: str
    last_transition_at: datetime
    ranking: MemoryRankingBreakdown

    @field_validator("record_id", mode="before")
    @classmethod
    def validate_record_id(cls, value: object) -> str:
        return _identifier(value, field="record_id")

    @field_validator("logical_key", "provenance_reference", mode="before")
    @classmethod
    def validate_references(cls, value: object, info) -> str:
        return _safe_reference(value, field=info.field_name)

    @field_validator("verification_confidence", mode="before")
    @classmethod
    def validate_verification_confidence(cls, value: object) -> object:
        if value is None:
            return value
        confidence = _finite_float(value, field="verification_confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("verification_confidence is invalid")
        return confidence

    @field_validator("last_transition_at", mode="before")
    @classmethod
    def validate_last_transition_at(cls, value: object) -> datetime:
        return _utc(value, field="last_transition_at")

    @model_validator(mode="after")
    def validate_trust_basis(self) -> MemoryContextEvidence:
        if self.trust_basis is MemoryTrustBasis.VERIFICATION:
            if (
                self.verification_subject is None
                or self.verification_confidence != 1.0
            ):
                raise ValueError("verification fields do not match trust basis")
        elif (
            self.verification_subject is not None
            or self.verification_confidence is not None
        ):
            raise ValueError("verification fields do not match trust basis")
        return self


class MemoryContext(_MemoryRetrievalContract):
    request_id: str
    project_id: str
    memory_id: str
    aggregate_revision: int = Field(ge=0)
    domains: tuple[MemoryDomain, ...]
    records: tuple[MemorySnapshotRecord, ...]
    evidence: tuple[MemoryContextEvidence, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    source_snapshot_fingerprint: str
    context_fingerprint: str

    @field_validator("request_id", "project_id", "memory_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("aggregate_revision", mode="before")
    @classmethod
    def validate_aggregate_revision(cls, value: object) -> int:
        return _integer(
            value,
            field="aggregate_revision",
            minimum=0,
            maximum=2**63 - 1,
        )

    @field_validator("domains", "records", "evidence", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @field_validator("domains")
    @classmethod
    def validate_domains(
        cls,
        value: tuple[MemoryDomain, ...],
    ) -> tuple[MemoryDomain, ...]:
        if not value:
            raise ValueError("domains must be non-empty")
        if len(value) != len(set(value)):
            raise ValueError("domains must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        confidence = _finite_float(value, field="confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence is invalid")
        return confidence

    @field_validator(
        "source_snapshot_fingerprint",
        "context_fingerprint",
        mode="before",
    )
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return _fingerprint(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_alignment_and_confidence(self) -> MemoryContext:
        record_ids = tuple(item.record_id for item in self.records)
        evidence_ids = tuple(item.record_id for item in self.evidence)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("context record IDs must be unique")
        if record_ids != evidence_ids:
            raise ValueError("records and evidence must align")
        if any(item.status is not MemoryStatus.VERIFIED for item in self.records):
            raise ValueError("context records must be verified")

        expected_confidence = 0.0
        if self.evidence:
            expected_confidence = min(
                1.0
                if item.trust_basis is MemoryTrustBasis.VERIFICATION
                else 0.5
                for item in self.evidence
            )
        if self.confidence != expected_confidence:
            raise ValueError("context confidence is invalid")
        return self
