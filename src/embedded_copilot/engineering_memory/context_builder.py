from __future__ import annotations

import copy
import math
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .context import MemoryContextEvidence, MemoryTrustBasis
from .fingerprint import canonical_fingerprint
from .ranking import RankedMemoryItem

_FINGERPRINT_PATTERN = re.compile(r"sha256:[a-f0-9]{64}\Z")


class _ContextBuilderContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _confidence(value: tuple[MemoryContextEvidence, ...]) -> float:
    if not value:
        return 0.0
    completeness: list[float] = []
    for item in value:
        if item.trust_basis is MemoryTrustBasis.VERIFICATION:
            if item.verification_confidence is None:
                raise ValueError("verification evidence confidence is invalid")
            completeness.append(item.verification_confidence)
        elif item.trust_basis is MemoryTrustBasis.HUMAN_APPROVAL:
            completeness.append(0.5)
        else:
            raise ValueError("evidence trust basis is invalid")
    return min(completeness)


def _validate_alignment(
    records: tuple[RankedMemoryItem, ...],
    evidence: tuple[MemoryContextEvidence, ...],
) -> None:
    record_ids = tuple(item.record_id for item in records)
    evidence_ids = tuple(item.record_id for item in evidence)
    if len(record_ids) != len(set(record_ids)) or len(evidence_ids) != len(
        set(evidence_ids)
    ):
        raise ValueError("context record IDs must be unique")
    if record_ids != evidence_ids:
        raise ValueError("records and evidence must align")
    for record, supporting in zip(records, evidence, strict=True):
        if (
            record.memory_type is not supporting.memory_type
            or record.logical_key != supporting.logical_key
            or record.ranking != supporting.ranking
        ):
            raise ValueError("records and evidence must align")


class _MemoryContextFingerprintMaterial(_ContextBuilderContract):
    records: tuple[RankedMemoryItem, ...]
    evidence: tuple[MemoryContextEvidence, ...]
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("records", "evidence", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)


def _context_fingerprint(
    records: tuple[RankedMemoryItem, ...],
    evidence: tuple[MemoryContextEvidence, ...],
    confidence: float,
) -> str:
    return canonical_fingerprint(
        _MemoryContextFingerprintMaterial(
            records=records,
            evidence=evidence,
            confidence=confidence,
        )
    )


class RankedMemoryContext(_ContextBuilderContract):
    records: tuple[RankedMemoryItem, ...]
    evidence: tuple[MemoryContextEvidence, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    context_fingerprint: str

    @field_validator("records", "evidence", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("confidence is invalid")
        return value

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context_fingerprint(cls, value: object) -> str:
        if type(value) is not str or _FINGERPRINT_PATTERN.fullmatch(value) is None:
            raise ValueError("context fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_context(self) -> RankedMemoryContext:
        _validate_alignment(self.records, self.evidence)
        expected_confidence = _confidence(self.evidence)
        if self.confidence != expected_confidence:
            raise ValueError("context confidence is invalid")
        expected_fingerprint = _context_fingerprint(
            self.records,
            self.evidence,
            self.confidence,
        )
        if self.context_fingerprint != expected_fingerprint:
            raise ValueError("context fingerprint does not match content")
        return self


def _checked_item(value: object) -> RankedMemoryItem:
    if not isinstance(value, RankedMemoryItem):
        raise ValueError("ranked memory item is invalid")  # noqa: TRY004
    return RankedMemoryItem.model_validate(copy.deepcopy(value))


def _checked_evidence(value: object) -> MemoryContextEvidence:
    if not isinstance(value, MemoryContextEvidence):
        raise ValueError("memory context evidence is invalid")  # noqa: TRY004
    return MemoryContextEvidence.model_validate(copy.deepcopy(value))


def build_memory_context(
    ranked_items: tuple[RankedMemoryItem, ...],
    *,
    evidence: tuple[MemoryContextEvidence, ...],
) -> RankedMemoryContext:
    _tuple(ranked_items, field="ranked_items")
    _tuple(evidence, field="evidence")
    checked_records = tuple(_checked_item(item) for item in ranked_items)
    checked_evidence = tuple(_checked_evidence(item) for item in evidence)
    _validate_alignment(checked_records, checked_evidence)
    confidence = _confidence(checked_evidence)
    fingerprint = _context_fingerprint(
        checked_records,
        checked_evidence,
        confidence,
    )
    return RankedMemoryContext(
        records=checked_records,
        evidence=checked_evidence,
        confidence=confidence,
        context_fingerprint=fingerprint,
    )
