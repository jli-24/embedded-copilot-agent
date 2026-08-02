"""Immutable contracts for deterministic engineering understanding."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_HTTPS_REFERENCE = re.compile(r"^https://[^\s/@:]+(?::[0-9]{1,5})?(?:/[^\s]*)?$")
_ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)


class _IntelligenceContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _key(value: object) -> str:
    if type(value) is not str or _KEY.fullmatch(value) is None:
        raise ValueError("key is invalid")
    return value


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not candidate or len(candidate) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ValueError(f"{field} is invalid")
    if _ABSOLUTE_PATH.search(candidate) or _SENSITIVE.search(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _reference(value: object) -> str:
    if type(value) is not str:
        raise ValueError("reference_id is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is not None:
        return candidate
    if (
        _HTTPS_REFERENCE.fullmatch(candidate) is not None
        and "?" not in candidate
        and "#" not in candidate
    ):
        return candidate
    raise ValueError("reference_id is invalid")


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _tokens(value: object, *, field: str) -> tuple[str, ...]:
    values = _tuple(value, field=field)
    checked = tuple(_token(item, field=field) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _references(value: object) -> tuple[str, ...]:
    values = _tuple(value, field="reference_ids")
    checked = tuple(_reference(item) for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError("reference_ids must be sorted and unique")
    return checked


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _finite(value: object, *, field: str) -> float:
    if type(value) not in {int, float} or type(value) is bool:
        raise ValueError(f"{field} is invalid")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} is invalid")
    return result


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class EngineeringKnowledgeSourceType(StrEnum):
    MEMORY = "MEMORY"
    RAG = "RAG"
    DATASHEET = "DATASHEET"
    WEB_RESEARCH = "WEB_RESEARCH"


class EvidenceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"


class DatasheetKnowledgeCategory(StrEnum):
    MCU_CAPABILITY = "MCU_CAPABILITY"
    GPIO = "GPIO"
    PERIPHERAL = "PERIPHERAL"
    INTERFACE = "INTERFACE"
    MEMORY = "MEMORY"
    POWER = "POWER"
    LIMITATION = "LIMITATION"


class WebResearchTopic(StrEnum):
    CHIP_INFORMATION = "CHIP_INFORMATION"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"
    APPLICATION_NOTE = "APPLICATION_NOTE"
    ENGINEERING_ARTICLE = "ENGINEERING_ARTICLE"


class EngineeringTaskDomain(StrEnum):
    HARDWARE = "HARDWARE"
    PCB = "PCB"
    FIRMWARE = "FIRMWARE"
    TESTING = "TESTING"
    OPTIMIZATION = "OPTIMIZATION"


class EstimatedEffort(StrEnum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class EngineeringIntelligenceStage(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    PLANNING = "PLANNING"
    KNOWLEDGE = "KNOWLEDGE"


class EngineeringProgressStatus(StrEnum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"


def project_context_fingerprint(
    *,
    project_id: str,
    name: str,
    summary: str,
    reference_ids: tuple[str, ...],
    source_fingerprint: str,
) -> str:
    return _fingerprint(
        {
            "project_id": project_id,
            "name": name,
            "summary": summary,
            "reference_ids": reference_ids,
            "source_fingerprint": source_fingerprint,
        }
    )


class EngineeringProjectContextProjection(_IntelligenceContract):
    project_id: str
    name: str
    summary: str
    reference_ids: tuple[str, ...]
    source_fingerprint: str
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _name = field_validator("name")(
        lambda value: _safe_text(value, field="name", maximum=128)
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary")
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _source_fingerprint = field_validator("source_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringProjectContextProjection:
        expected = project_context_fingerprint(
            project_id=self.project_id,
            name=self.name,
            summary=self.summary,
            reference_ids=self.reference_ids,
            source_fingerprint=self.source_fingerprint,
        )
        if self.fingerprint != expected:
            raise ValueError("project context fingerprint mismatch")
        return self


class EngineeringRequirementRequest(_IntelligenceContract):
    project: EngineeringProjectContextProjection
    session_id: str
    message_id: str
    requirement_summary: str
    requested_at: datetime

    @field_validator("session_id", "message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_summary = field_validator("requirement_summary")(
        lambda value: _safe_text(value, field="requirement_summary", maximum=2048)
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


class RequirementConstraint(_IntelligenceContract):
    key: str
    value: str

    _key_value = field_validator("key")(lambda value: _token(value, field="key"))
    _value = field_validator("value")(
        lambda value: _safe_text(value, field="value", maximum=128)
    )


def requirement_document_fingerprint(
    *,
    project_id: str,
    session_id: str,
    message_id: str,
    product: str,
    functional_requirements: tuple[str, ...],
    performance_requirements: tuple[str, ...],
    hardware_constraints: tuple[RequirementConstraint, ...],
    software_constraints: tuple[str, ...],
    power_requirements: tuple[str, ...],
    communication_requirements: tuple[str, ...],
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "project_id": project_id,
            "session_id": session_id,
            "message_id": message_id,
            "product": product,
            "functional_requirements": functional_requirements,
            "performance_requirements": performance_requirements,
            "hardware_constraints": hardware_constraints,
            "software_constraints": software_constraints,
            "power_requirements": power_requirements,
            "communication_requirements": communication_requirements,
            "review_required": review_required,
        }
    )


class EngineeringRequirementDocument(_IntelligenceContract):
    project_id: str
    session_id: str
    message_id: str
    product: str
    functional_requirements: tuple[str, ...]
    performance_requirements: tuple[str, ...]
    hardware_constraints: tuple[RequirementConstraint, ...]
    software_constraints: tuple[str, ...]
    power_requirements: tuple[str, ...]
    communication_requirements: tuple[str, ...]
    review_required: Literal[True] = True
    fingerprint: str

    @field_validator("project_id", "session_id", "message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _product = field_validator("product")(lambda value: _token(value, field="product"))
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator(
        "functional_requirements",
        "performance_requirements",
        "software_constraints",
        "power_requirements",
        "communication_requirements",
        mode="before",
    )
    @classmethod
    def validate_token_tuples(cls, value: object, info) -> tuple[str, ...]:
        return _tokens(value, field=info.field_name)

    @field_validator("hardware_constraints", mode="before")
    @classmethod
    def validate_constraint_tuple(cls, value: object) -> object:
        return _tuple(value, field="hardware_constraints")

    @field_validator("hardware_constraints")
    @classmethod
    def validate_constraints(
        cls, value: tuple[RequirementConstraint, ...]
    ) -> tuple[RequirementConstraint, ...]:
        keys = tuple((item.key, item.value) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("hardware constraints must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringRequirementDocument:
        expected = requirement_document_fingerprint(
            project_id=self.project_id,
            session_id=self.session_id,
            message_id=self.message_id,
            product=self.product,
            functional_requirements=self.functional_requirements,
            performance_requirements=self.performance_requirements,
            hardware_constraints=self.hardware_constraints,
            software_constraints=self.software_constraints,
            power_requirements=self.power_requirements,
            communication_requirements=self.communication_requirements,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("requirement fingerprint mismatch")
        return self


class EngineeringTask(_IntelligenceContract):
    task_id: str
    domain: EngineeringTaskDomain
    summary: str
    dependencies: tuple[str, ...]
    estimated_effort: EstimatedEffort
    engineering_risk: str
    milestone: str

    _task_id = field_validator("task_id")(
        lambda value: _identifier(value, field="task_id")
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=256)
    )
    _engineering_risk = field_validator("engineering_risk")(
        lambda value: _token(value, field="engineering_risk")
    )
    _milestone = field_validator("milestone")(
        lambda value: _token(value, field="milestone")
    )

    @field_validator("dependencies", mode="before")
    @classmethod
    def validate_dependencies(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="dependencies")
        checked = tuple(_identifier(item, field="dependency") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("dependencies must be sorted and unique")
        return checked


def project_plan_fingerprint(
    *,
    project_id: str,
    requirement_fingerprint: str,
    tasks: tuple[EngineeringTask, ...],
    milestones: tuple[str, ...],
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "project_id": project_id,
            "requirement_fingerprint": requirement_fingerprint,
            "tasks": tasks,
            "milestones": milestones,
            "review_required": review_required,
        }
    )


class EngineeringProjectPlan(_IntelligenceContract):
    project_id: str
    requirement_fingerprint: str
    tasks: tuple[EngineeringTask, ...] = Field(min_length=1, max_length=64)
    milestones: tuple[str, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _milestones = field_validator("milestones", mode="before")(
        lambda value: _tokens(value, field="milestones")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_task_tuple(cls, value: object) -> object:
        return _tuple(value, field="tasks")

    @model_validator(mode="after")
    def validate_plan(self) -> EngineeringProjectPlan:
        task_ids = tuple(item.task_id for item in self.tasks)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValueError("tasks must be sorted and unique")
        known = set(task_ids)
        for task in self.tasks:
            if task.task_id in task.dependencies or not set(task.dependencies).issubset(
                known
            ):
                raise ValueError("task dependency is invalid")
        expected = project_plan_fingerprint(
            project_id=self.project_id,
            requirement_fingerprint=self.requirement_fingerprint,
            tasks=self.tasks,
            milestones=self.milestones,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("plan fingerprint mismatch")
        return self


def engineering_evidence_fingerprint(
    *,
    evidence_id: str,
    source_type: EngineeringKnowledgeSourceType,
    fact_type: str,
    key: str,
    value: str,
    summary: str,
    status: EvidenceStatus,
    confidence: float,
    reference_ids: tuple[str, ...],
    observed_at: datetime,
) -> str:
    return _fingerprint(
        {
            "evidence_id": evidence_id,
            "source_type": source_type,
            "fact_type": fact_type,
            "key": key,
            "value": value,
            "summary": summary,
            "status": status,
            "confidence": confidence,
            "reference_ids": reference_ids,
            "observed_at": observed_at,
        }
    )


class EngineeringKnowledgeEvidence(_IntelligenceContract):
    evidence_id: str
    source_type: EngineeringKnowledgeSourceType
    fact_type: str
    key: str
    value: str
    summary: str
    status: EvidenceStatus
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    reference_ids: tuple[str, ...]
    observed_at: datetime
    fingerprint: str

    _evidence_id = field_validator("evidence_id")(
        lambda value: _identifier(value, field="evidence_id")
    )
    _fact_type = field_validator("fact_type")(
        lambda value: _token(value, field="fact_type")
    )
    _key_value = field_validator("key")(_key)
    _value = field_validator("value")(
        lambda value: _safe_text(value, field="value", maximum=256)
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=512)
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _observed_at = field_validator("observed_at")(
        lambda value: _utc(value, field="observed_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        result = _finite(value, field="confidence")
        if not 0.0 <= result <= 1.0:
            raise ValueError("confidence is invalid")
        return result

    @model_validator(mode="after")
    def validate_evidence(self) -> EngineeringKnowledgeEvidence:
        if self.status is EvidenceStatus.VERIFIED and self.confidence != 1.0:
            raise ValueError("verified evidence requires confidence 1.0")
        expected = engineering_evidence_fingerprint(
            evidence_id=self.evidence_id,
            source_type=self.source_type,
            fact_type=self.fact_type,
            key=self.key,
            value=self.value,
            summary=self.summary,
            status=self.status,
            confidence=self.confidence,
            reference_ids=self.reference_ids,
            observed_at=self.observed_at,
        )
        if self.fingerprint != expected:
            raise ValueError("evidence fingerprint mismatch")
        return self


def datasheet_projection_fingerprint(
    *,
    source_id: str,
    categories: tuple[DatasheetKnowledgeCategory, ...],
    facts: tuple[EngineeringKnowledgeEvidence, ...],
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "source_id": source_id,
            "categories": categories,
            "facts": facts,
            "review_required": review_required,
        }
    )


class DatasheetKnowledgeProjection(_IntelligenceContract):
    source_id: str
    categories: tuple[DatasheetKnowledgeCategory, ...]
    facts: tuple[EngineeringKnowledgeEvidence, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _source_id = field_validator("source_id")(
        lambda value: _identifier(value, field="source_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("categories", "facts", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> DatasheetKnowledgeProjection:
        if self.categories != tuple(DatasheetKnowledgeCategory):
            raise ValueError("datasheet categories are invalid")
        ids = tuple(item.evidence_id for item in self.facts)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("datasheet facts must be sorted and unique")
        if any(
            item.source_type is not EngineeringKnowledgeSourceType.DATASHEET
            or item.status is not EvidenceStatus.CANDIDATE
            for item in self.facts
        ):
            raise ValueError("datasheet facts must remain candidates")
        expected = datasheet_projection_fingerprint(
            source_id=self.source_id,
            categories=self.categories,
            facts=self.facts,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("datasheet projection fingerprint mismatch")
        return self


class WebResearchRequest(_IntelligenceContract):
    query_id: str
    project_id: str
    topic: WebResearchTopic
    query_summary: str
    requested_at: datetime

    @field_validator("query_id", "project_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _query_summary = field_validator("query_summary")(
        lambda value: _safe_text(value, field="query_summary", maximum=512)
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


def web_result_fingerprint(
    *,
    query_id: str,
    topic: WebResearchTopic,
    findings: tuple[EngineeringKnowledgeEvidence, ...],
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "query_id": query_id,
            "topic": topic,
            "findings": findings,
            "review_required": review_required,
        }
    )


class WebResearchResult(_IntelligenceContract):
    query_id: str
    topic: WebResearchTopic
    findings: tuple[EngineeringKnowledgeEvidence, ...]
    review_required: Literal[True] = True
    fingerprint: str

    _query_id = field_validator("query_id")(
        lambda value: _identifier(value, field="query_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("findings", mode="before")
    @classmethod
    def validate_findings_tuple(cls, value: object) -> object:
        return _tuple(value, field="findings")

    @model_validator(mode="after")
    def validate_result(self) -> WebResearchResult:
        ids = tuple(item.evidence_id for item in self.findings)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("web findings must be sorted and unique")
        if any(
            item.source_type is not EngineeringKnowledgeSourceType.WEB_RESEARCH
            for item in self.findings
        ):
            raise ValueError("web finding source is invalid")
        expected = web_result_fingerprint(
            query_id=self.query_id,
            topic=self.topic,
            findings=self.findings,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("web result fingerprint mismatch")
        return self


class EngineeringDecisionProjection(_IntelligenceContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    item: str
    choice: str
    reason: str
    evidence_ids: tuple[str, ...]
    review_required: Literal[True] = True

    _item = field_validator("item")(lambda value: _token(value, field="item"))
    _choice = field_validator("choice")(
        lambda value: _safe_text(value, field="choice", maximum=128)
    )
    _reason = field_validator("reason")(lambda value: _token(value, field="reason"))

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def validate_evidence_ids(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="evidence_ids")
        checked = tuple(_identifier(item, field="evidence_id") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("evidence_ids must be sorted and unique")
        return checked


class EngineeringContextRequest(_IntelligenceContract):
    project: EngineeringProjectContextProjection
    requirement: EngineeringRequirementDocument
    plan: EngineeringProjectPlan
    evidence: tuple[EngineeringKnowledgeEvidence, ...]
    requested_at: datetime

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence_tuple(cls, value: object) -> object:
        return _tuple(value, field="evidence")

    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


def context_snapshot_fingerprint(
    *,
    project: EngineeringProjectContextProjection,
    requirement_fingerprint: str,
    plan_fingerprint: str,
    evidence: tuple[EngineeringKnowledgeEvidence, ...],
    decisions: tuple[EngineeringDecisionProjection, ...],
    confidence: float,
    conflict_count: int,
    review_required: bool,
) -> str:
    return _fingerprint(
        {
            "project": project,
            "requirement_fingerprint": requirement_fingerprint,
            "plan_fingerprint": plan_fingerprint,
            "evidence": evidence,
            "decisions": decisions,
            "confidence": confidence,
            "conflict_count": conflict_count,
            "review_required": review_required,
        }
    )


class EngineeringContextSnapshot(_IntelligenceContract):
    project: EngineeringProjectContextProjection
    requirement_fingerprint: str
    plan_fingerprint: str
    evidence: tuple[EngineeringKnowledgeEvidence, ...]
    decisions: tuple[EngineeringDecisionProjection, ...]
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    conflict_count: int = Field(ge=0)
    review_required: Literal[True] = True
    fingerprint: str

    _requirement_fingerprint = field_validator("requirement_fingerprint")(
        _fingerprint_value
    )
    _plan_fingerprint = field_validator("plan_fingerprint")(_fingerprint_value)
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("evidence", "decisions", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        result = _finite(value, field="confidence")
        if not 0.0 <= result <= 1.0:
            raise ValueError("confidence is invalid")
        return result

    @field_validator("conflict_count")
    @classmethod
    def validate_conflict_count(cls, value: int) -> int:
        if type(value) is not int or value < 0:
            raise ValueError("conflict_count is invalid")
        return value

    @model_validator(mode="after")
    def validate_snapshot(self) -> EngineeringContextSnapshot:
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if evidence_ids != tuple(sorted(evidence_ids)) or len(evidence_ids) != len(
            set(evidence_ids)
        ):
            raise ValueError("context evidence must be sorted and unique")
        decision_keys = tuple((item.item, item.choice) for item in self.decisions)
        if decision_keys != tuple(sorted(decision_keys)) or len(decision_keys) != len(
            set(decision_keys)
        ):
            raise ValueError("decisions must be sorted and unique")
        expected = context_snapshot_fingerprint(
            project=self.project,
            requirement_fingerprint=self.requirement_fingerprint,
            plan_fingerprint=self.plan_fingerprint,
            evidence=self.evidence,
            decisions=self.decisions,
            confidence=self.confidence,
            conflict_count=self.conflict_count,
            review_required=self.review_required,
        )
        if self.fingerprint != expected:
            raise ValueError("context fingerprint mismatch")
        return self


def progress_event_fingerprint(
    *,
    sequence: int,
    project_id: str,
    session_id: str,
    stage: EngineeringIntelligenceStage,
    status: EngineeringProgressStatus,
    progress: float,
    count: int,
    timestamp: datetime,
) -> str:
    return _fingerprint(
        {
            "sequence": sequence,
            "project_id": project_id,
            "session_id": session_id,
            "stage": stage,
            "status": status,
            "progress": progress,
            "count": count,
            "timestamp": timestamp,
        }
    )


class EngineeringIntelligenceProgressEvent(_IntelligenceContract):
    sequence: int = Field(ge=1, le=32)
    project_id: str
    session_id: str
    stage: EngineeringIntelligenceStage
    status: EngineeringProgressStatus
    progress: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    count: int = Field(ge=0)
    timestamp: datetime
    fingerprint: str

    @field_validator("project_id", "session_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("sequence", "count")
    @classmethod
    def validate_counts(cls, value: int, info) -> int:
        minimum = 1 if info.field_name == "sequence" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("progress", mode="before")
    @classmethod
    def validate_progress(cls, value: object) -> float:
        result = _finite(value, field="progress")
        if not 0.0 <= result <= 1.0:
            raise ValueError("progress is invalid")
        return result

    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringIntelligenceProgressEvent:
        expected = progress_event_fingerprint(
            sequence=self.sequence,
            project_id=self.project_id,
            session_id=self.session_id,
            stage=self.stage,
            status=self.status,
            progress=self.progress,
            count=self.count,
            timestamp=self.timestamp,
        )
        if self.fingerprint != expected:
            raise ValueError("progress fingerprint mismatch")
        return self


class EngineeringIntelligenceRequest(_IntelligenceContract):
    project: EngineeringProjectContextProjection
    session_id: str
    message_id: str
    requirement_summary: str
    evidence: tuple[EngineeringKnowledgeEvidence, ...]
    requested_at: datetime

    @field_validator("session_id", "message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requirement_summary = field_validator("requirement_summary")(
        lambda value: _safe_text(value, field="requirement_summary", maximum=2048)
    )
    _evidence = field_validator("evidence", mode="before")(
        lambda value: _tuple(value, field="evidence")
    )
    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


def intelligence_snapshot_fingerprint(
    *,
    project: EngineeringProjectContextProjection,
    requirement: EngineeringRequirementDocument,
    plan: EngineeringProjectPlan,
    context: EngineeringContextSnapshot,
    progress_events: tuple[EngineeringIntelligenceProgressEvent, ...],
) -> str:
    return _fingerprint(
        {
            "project": project,
            "requirement": requirement,
            "plan": plan,
            "context": context,
            "progress_events": progress_events,
        }
    )


class EngineeringIntelligenceSnapshot(_IntelligenceContract):
    project: EngineeringProjectContextProjection
    requirement: EngineeringRequirementDocument
    plan: EngineeringProjectPlan
    context: EngineeringContextSnapshot
    progress_events: tuple[EngineeringIntelligenceProgressEvent, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fingerprint_value)

    @field_validator("progress_events", mode="before")
    @classmethod
    def validate_progress_tuple(cls, value: object) -> object:
        return _tuple(value, field="progress_events")

    @model_validator(mode="after")
    def validate_snapshot(self) -> EngineeringIntelligenceSnapshot:
        if any(
            value != self.project.project_id
            for value in (
                self.requirement.project_id,
                self.plan.project_id,
                self.context.project.project_id,
            )
        ):
            raise ValueError("project binding mismatch")
        sequences = tuple(item.sequence for item in self.progress_events)
        if sequences != tuple(range(1, len(sequences) + 1)):
            raise ValueError("progress sequence mismatch")
        expected = intelligence_snapshot_fingerprint(
            project=self.project,
            requirement=self.requirement,
            plan=self.plan,
            context=self.context,
            progress_events=self.progress_events,
        )
        if self.fingerprint != expected:
            raise ValueError("intelligence fingerprint mismatch")
        return self
