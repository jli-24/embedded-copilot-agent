from __future__ import annotations

import re
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator

from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace
from embedded_copilot.schemas.result import ContractModel

_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SENSITIVE_SUMMARY = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=]"
    r"|[A-Za-z]:[\\/]|\\\\|file://)",
    re.IGNORECASE,
)


class KnowledgeSourceType(StrEnum):
    DATASHEET = "datasheet"
    OFFICIAL_DOC = "official_doc"
    GITHUB = "github"
    WEB = "web"
    USER_UPLOAD = "user_upload"
    GENERATED = "generated"


class _KnowledgeIntelligenceModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class KnowledgeEvidence(_KnowledgeIntelligenceModel):
    source_id: str
    source_type: KnowledgeSourceType
    summary: str
    relevance_score: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
    )

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("source_id must be a string")
        candidate = value.strip()
        if not _SOURCE_ID.fullmatch(candidate):
            raise ValueError("source_id is invalid")
        return candidate

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("summary must be a string")
        candidate = " ".join(value.split())
        if (
            not candidate
            or len(candidate) > 512
            or _SENSITIVE_SUMMARY.search(candidate)
        ):
            raise ValueError("summary is unsafe")
        return candidate


class KnowledgeRetrieval(_KnowledgeIntelligenceModel):
    evidence: tuple[KnowledgeEvidence, ...] = ()
    trace: KnowledgeTrace


def project_result(result: KnowledgeResult) -> KnowledgeEvidence:
    validated = KnowledgeResult.model_validate(result.model_dump(mode="python"))
    normalized = " ".join(validated.content.split())[:512]
    return KnowledgeEvidence(
        source_id=validated.id,
        source_type=_source_type(validated),
        summary=normalized,
        relevance_score=validated.score,
    )


def _source_type(result: KnowledgeResult) -> KnowledgeSourceType:
    if result.source is KnowledgeSource.GITHUB:
        return KnowledgeSourceType.GITHUB
    if result.source is KnowledgeSource.WEB:
        return KnowledgeSourceType.WEB
    explicit = result.metadata.get("source_type")
    if explicit is None:
        return KnowledgeSourceType.USER_UPLOAD
    try:
        source_type = KnowledgeSourceType(explicit)
    except (TypeError, ValueError):
        raise ValueError("knowledge source type is invalid") from None
    if source_type in {KnowledgeSourceType.GITHUB, KnowledgeSourceType.WEB}:
        raise ValueError("local knowledge source type is invalid")
    if source_type is KnowledgeSourceType.GENERATED:
        original_source_id = result.metadata.get("original_source_id")
        if (
            not isinstance(original_source_id, str)
            or not _SOURCE_ID.fullmatch(original_source_id.strip())
            or original_source_id.strip().casefold() == result.id.casefold()
        ):
            raise ValueError("generated knowledge requires an original source binding")
    return source_type
