from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from embedded_copilot.agents.types import AgentTask
from embedded_copilot.engineering_memory.context_builder import RankedMemoryContext
from embedded_copilot.engineering_memory.fingerprint import canonical_fingerprint
from embedded_copilot.knowledge.models import KnowledgeQuery, KnowledgeResult
from embedded_copilot.knowledge.source import KnowledgeSourceType
from embedded_copilot.schemas.result import ContractModel


SupervisorTraceStage = Literal[
    "task_parsed",
    "knowledge_query_built",
    "gateway_retrieved",
    "context_built",
    "agent_routed",
    "finished",
]
SupervisorTraceStatus = Literal["success", "error"]

_FORBIDDEN_CONTEXT_METADATA_KEYS = frozenset(
    {
        "aggregate",
        "approval",
        "approval_body",
        "audit",
        "audit_metadata",
        "evidence",
        "finding",
        "finding_body",
        "findings",
        "memory_evidence",
        "memory_id",
        "memory_records",
        "payload",
        "provenance_reference",
        "raw_verification_result",
        "record_id",
        "record_ids",
        "runtime",
        "runtime_object",
        "source_reference",
        "store_aggregate",
        "verification_result",
    }
)
_OMIT_CONTEXT_METADATA = object()


def _normalized_metadata_key(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _forbidden_metadata_key(value: object) -> bool:
    if type(value) is not str:
        return True
    normalized = _normalized_metadata_key(value)
    return (
        normalized in _FORBIDDEN_CONTEXT_METADATA_KEYS
        or "fingerprint" in normalized
    )


def _contains_unsafe_metadata(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            _forbidden_metadata_key(key) or _contains_unsafe_metadata(item)
            for key, item in value.items()
        )
    if type(value) in (list, tuple):
        return any(_contains_unsafe_metadata(item) for item in value)
    return type(value) not in (bool, float, int, str, type(None))


def _project_metadata_value(value: object) -> object:
    if isinstance(value, Mapping):
        projected: dict[str, object] = {}
        for key, item in value.items():
            if _forbidden_metadata_key(key):
                continue
            checked = _project_metadata_value(item)
            if checked is not _OMIT_CONTEXT_METADATA:
                projected[key] = checked
        return projected
    if type(value) is list:
        return [
            checked
            for item in value
            if (checked := _project_metadata_value(item))
            is not _OMIT_CONTEXT_METADATA
        ]
    if type(value) is tuple:
        return tuple(
            checked
            for item in value
            if (checked := _project_metadata_value(item))
            is not _OMIT_CONTEXT_METADATA
        )
    if type(value) in (bool, float, int, str, type(None)):
        return copy.deepcopy(value)
    return _OMIT_CONTEXT_METADATA


def project_safe_supervisor_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("supervisor metadata is invalid")
    projected = _project_metadata_value(value)
    if not isinstance(projected, dict):
        raise ValueError("supervisor metadata is invalid")
    return projected


class KnowledgeContext(ContractModel):
    query: KnowledgeQuery
    retrieved_documents: tuple[KnowledgeResult, ...] = ()
    summary: str = Field(min_length=1)

    @field_validator("query", "retrieved_documents", mode="before")
    @classmethod
    def isolate_nested_models(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator("summary", mode="before")
    @classmethod
    def strip_summary(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SupervisorTraceEvent(ContractModel):
    stage: SupervisorTraceStage
    status: SupervisorTraceStatus
    target: str = Field(min_length=1)
    domains: tuple[str, ...] = ()
    count: int = Field(default=0, ge=0)

    @field_validator("stage", "status", "target", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("domains", mode="before")
    @classmethod
    def isolate_domains(cls, value: object) -> object:
        return copy.deepcopy(value)


class ExecutionContext(ContractModel):
    task: AgentTask
    knowledge_context: KnowledgeContext
    trace: tuple[SupervisorTraceEvent, ...] = ()
    execution_id: UUID

    @field_validator("task", "knowledge_context", "trace", mode="before")
    @classmethod
    def isolate_nested_models(cls, value: object) -> object:
        return copy.deepcopy(value)

    @model_validator(mode="after")
    def reject_unsafe_task_metadata(self) -> ExecutionContext:
        if _contains_unsafe_metadata(self.task.metadata):
            raise ValueError("execution context task metadata is invalid")
        return self


_PLANNING_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_LOCAL_REFERENCE = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://)", re.IGNORECASE)
_SENSITIVE_REFERENCE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)
_FUSION_FINGERPRINT = re.compile(r"sha256:[a-f0-9]{64}\Z")


class _PlanningContextContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class PlanningKnowledgeEvidence(_PlanningContextContract):
    source_id: str
    source_type: KnowledgeSourceType
    reference: str
    trust_level: float = Field(ge=0.0, le=1.0)

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        if type(value) is not str:
            raise ValueError("source_id is invalid")
        candidate = value.strip()
        if _PLANNING_SOURCE_ID.fullmatch(candidate) is None:
            raise ValueError("source_id is invalid")
        return candidate

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        if type(value) is not str:
            raise ValueError("reference is invalid")
        candidate = value.strip()
        if (
            not candidate
            or len(candidate) > 512
            or "\x00" in candidate
            or "\r" in candidate
            or "\n" in candidate
            or _LOCAL_REFERENCE.search(candidate) is not None
            or _SENSITIVE_REFERENCE.search(candidate) is not None
        ):
            raise ValueError("reference is invalid")
        return candidate

    @field_validator("trust_level", mode="before")
    @classmethod
    def validate_trust_level(cls, value: object) -> float:
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError("trust_level is invalid")
        return value


class PlanningKnowledgeContext(_PlanningContextContract):
    sources: tuple[PlanningKnowledgeEvidence, ...] = ()

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources_tuple(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("sources must be a tuple")
        return value

    @field_validator("sources")
    @classmethod
    def validate_unique_sources(
        cls,
        value: tuple[PlanningKnowledgeEvidence, ...],
    ) -> tuple[PlanningKnowledgeEvidence, ...]:
        source_ids = tuple(item.source_id for item in value)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("knowledge source IDs must be unique")
        return value


class _FusionFingerprintMaterial(_PlanningContextContract):
    schema_version: Literal["1.0"] = "1.0"
    knowledge_fingerprint: str | None
    memory_fingerprint: str | None


def _knowledge_confidence(value: PlanningKnowledgeContext) -> float:
    if not value.sources:
        return 0.0
    return min(item.trust_level for item in value.sources)


def _fusion_confidence(
    knowledge_context: PlanningKnowledgeContext | None,
    memory_context: RankedMemoryContext | None,
) -> float:
    available: list[float] = []
    if knowledge_context is not None and knowledge_context.sources:
        available.append(_knowledge_confidence(knowledge_context))
    if memory_context is not None and memory_context.records:
        available.append(memory_context.confidence)
    return min(available) if available else 0.0


def _fusion_fingerprint(
    knowledge_context: PlanningKnowledgeContext | None,
    memory_context: RankedMemoryContext | None,
) -> str:
    knowledge_fingerprint = (
        canonical_fingerprint(knowledge_context)
        if knowledge_context is not None
        else None
    )
    memory_fingerprint = (
        memory_context.context_fingerprint if memory_context is not None else None
    )
    return canonical_fingerprint(
        _FusionFingerprintMaterial(
            knowledge_fingerprint=knowledge_fingerprint,
            memory_fingerprint=memory_fingerprint,
        )
    )


class EngineeringPlanningContext(_PlanningContextContract):
    knowledge_context: PlanningKnowledgeContext | None
    memory_context: RankedMemoryContext | None
    confidence: float = Field(ge=0.0, le=1.0)
    context_fingerprint: str

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        if (
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
        ):
            raise ValueError("confidence is invalid")
        return value

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context_fingerprint(cls, value: object) -> str:
        if type(value) is not str or _FUSION_FINGERPRINT.fullmatch(value) is None:
            raise ValueError("context fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_derived_fields(self) -> EngineeringPlanningContext:
        expected_confidence = _fusion_confidence(
            self.knowledge_context,
            self.memory_context,
        )
        if self.confidence != expected_confidence:
            raise ValueError("planning context confidence is invalid")
        expected_fingerprint = _fusion_fingerprint(
            self.knowledge_context,
            self.memory_context,
        )
        if self.context_fingerprint != expected_fingerprint:
            raise ValueError("planning context fingerprint does not match content")
        return self


def _checked_knowledge_context(
    value: PlanningKnowledgeContext | None,
) -> PlanningKnowledgeContext | None:
    if value is None:
        return None
    if not isinstance(value, PlanningKnowledgeContext):
        raise ValueError("knowledge context is invalid")  # noqa: TRY004
    return PlanningKnowledgeContext.model_validate(copy.deepcopy(value))


def _checked_memory_context(
    value: RankedMemoryContext | None,
) -> RankedMemoryContext | None:
    if value is None:
        return None
    if not isinstance(value, RankedMemoryContext):
        raise ValueError("memory context is invalid")  # noqa: TRY004
    return RankedMemoryContext.model_validate(copy.deepcopy(value))


def build_engineering_planning_context(
    *,
    knowledge_context: PlanningKnowledgeContext | None,
    memory_context: RankedMemoryContext | None,
) -> EngineeringPlanningContext:
    checked_knowledge = _checked_knowledge_context(knowledge_context)
    checked_memory = _checked_memory_context(memory_context)
    confidence = _fusion_confidence(checked_knowledge, checked_memory)
    fingerprint = _fusion_fingerprint(checked_knowledge, checked_memory)
    return EngineeringPlanningContext(
        knowledge_context=checked_knowledge,
        memory_context=checked_memory,
        confidence=confidence,
        context_fingerprint=fingerprint,
    )


SupervisorMemoryTraceKind = Literal[
    "retrieval_attempted",
    "retrieval_succeeded",
    "retrieval_failed",
]


class SupervisorMemoryTraceEvent(_PlanningContextContract):
    event: SupervisorMemoryTraceKind
    memory_count: int = Field(ge=0)

    @field_validator("memory_count", mode="before")
    @classmethod
    def validate_memory_count(cls, value: object) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("memory_count is invalid")
        return value


SupervisorFallbackTraceKind = Literal[
    "memory_failed",
    "knowledge_failed",
    "fusion_failed",
    "fallback_used",
]
SupervisorFallbackStage = Literal[
    "MemoryUnavailable",
    "KnowledgeUnavailable",
    "FusionUnavailable",
]


class SupervisorFallbackTraceEvent(_PlanningContextContract):
    event: SupervisorFallbackTraceKind
    stage: SupervisorFallbackStage
    memory_count: int = Field(ge=0)

    @field_validator("memory_count", mode="before")
    @classmethod
    def validate_memory_count(cls, value: object) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("memory_count is invalid")
        return value


SupervisorKnowledgeTraceStage = Literal["retrieval"]
SupervisorKnowledgeTraceStatus = Literal["success", "failed"]
SupervisorKnowledgeTraceSource = Literal[
    "datasheet",
    "official_doc",
    "github",
    "web",
    "user_upload",
    "generated",
    "mixed",
    "none",
]


class SupervisorKnowledgeTraceEvent(_PlanningContextContract):
    sequence: int = Field(ge=1)
    stage: SupervisorKnowledgeTraceStage
    status: SupervisorKnowledgeTraceStatus
    count: int = Field(ge=0)
    source_type: SupervisorKnowledgeTraceSource

    @field_validator("sequence", "count", mode="before")
    @classmethod
    def validate_counts(cls, value: object, info) -> int:
        minimum = 1 if info.field_name == "sequence" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"{info.field_name} is invalid")
        return value
