from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field, field_validator, model_validator

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.integration.safety import (
    is_safe_relative_path,
    is_safe_report_text,
    safe_optional_text,
    safe_source_fragment,
    safe_text_items,
)
from embedded_copilot.pcb.models import PCBReviewReport, UnifiedPCBModel
from embedded_copilot.schemas.result import ContractModel


IntegrationAgentName: TypeAlias = Literal[
    "FirmwareAgent",
    "HardwareAgent",
    "PCBAgent",
    "DebugAgent",
]
IntegrationSourceAgent: TypeAlias = Literal[
    "SupervisorAgent",
    "FirmwareAgent",
    "HardwareAgent",
    "PCBAgent",
    "DebugAgent",
]
IntegrationTraceStage: TypeAlias = Literal[
    "input_analyzed",
    "agent_planned",
    "knowledge_consumed",
    "agent_executed",
    "report_aggregated",
]
IntegrationTraceStatus: TypeAlias = Literal["success", "error"]


class _IntegrationModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )


def _validate_safe_source_id(value: object) -> object:
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not is_safe_report_text(candidate):
        raise ValueError("integration source id contains unsafe content")
    return candidate


class IntegrationTraceEvent(_IntegrationModel):
    sequence: int = Field(ge=1)
    stage: IntegrationTraceStage
    status: IntegrationTraceStatus
    source_agent: IntegrationSourceAgent
    source_id: str = Field(min_length=1, max_length=160)

    @field_validator("source_id", mode="before")
    @classmethod
    def strip_source_id(cls, value: object) -> object:
        return _validate_safe_source_id(value)


class IntegrationKnowledgeContext(_IntegrationModel):
    source_ids: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    result_count: int = Field(ge=0)
    summary: str = Field(min_length=1)

    @field_validator("source_ids", "sources", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        validated = tuple(_validate_safe_source_id(item) for item in value)
        return validated

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if not is_safe_report_text(candidate):
            raise ValueError("integration knowledge summary contains unsafe content")
        return candidate

    @model_validator(mode="after")
    def validate_result_count(self) -> "IntegrationKnowledgeContext":
        if self.result_count != len(self.source_ids):
            raise ValueError("knowledge result count does not match source ids")
        if len(self.sources) != len(self.source_ids):
            raise ValueError("knowledge sources do not match source ids")
        return self


def _contains_unsafe_text(value: object) -> bool:
    if isinstance(value, str):
        return not is_safe_report_text(value)
    if isinstance(value, Mapping):
        return any(_contains_unsafe_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_unsafe_text(item) for item in value)
    return False


class _SafeEvidenceModel(_IntegrationModel):
    @model_validator(mode="after")
    def validate_safe_content(self) -> "_SafeEvidenceModel":
        if _contains_unsafe_text(self.model_dump(mode="python")):
            raise ValueError("integration evidence contains unsafe content")
        return self


class FirmwareExecutionEvidence(_SafeEvidenceModel):
    kind: Literal["firmware"] = "firmware"
    project_name: str | None = None
    platform: str | None = None
    framework: str | None = None
    file_paths: tuple[str, ...] = ()
    structure: tuple[str, ...] = ()

    @field_validator("file_paths")
    @classmethod
    def validate_file_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not is_safe_relative_path(item) for item in value):
            raise ValueError("integration evidence contains unsafe file path")
        return value


class HardwareExecutionEvidence(_SafeEvidenceModel):
    kind: Literal["hardware"] = "hardware"
    project_name: str | None = None
    platform: str | None = None
    mcu: str | None = None
    components: tuple[str, ...] = ()
    interfaces: tuple[str, ...] = ()
    power_requirements: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    rationale: str | None = None


class FindingExecutionEvidence(_SafeEvidenceModel):
    source_id: str = Field(min_length=1, max_length=160)
    category: str
    severity: str
    description: str
    evidence: tuple[str, ...] = ()
    recommendation: str


class RecommendationExecutionEvidence(_SafeEvidenceModel):
    source_id: str = Field(min_length=1, max_length=160)
    text: str


class PCBExecutionEvidence(_SafeEvidenceModel):
    kind: Literal["pcb"] = "pcb"
    project_name: str | None = None
    platform: str | None = None
    summary: str | None = None
    findings: tuple[FindingExecutionEvidence, ...] = ()
    passed_rules: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class DebugExecutionEvidence(_SafeEvidenceModel):
    kind: Literal["debug"] = "debug"
    project_name: str | None = None
    platform: str | None = None
    error_type: str | None = None
    summary: str | None = None
    findings: tuple[FindingExecutionEvidence, ...] = ()
    recommendations: tuple[RecommendationExecutionEvidence, ...] = ()


DomainExecutionEvidence: TypeAlias = Annotated[
    FirmwareExecutionEvidence
    | HardwareExecutionEvidence
    | PCBExecutionEvidence
    | DebugExecutionEvidence,
    Field(discriminator="kind"),
]


def _agent_source_id(agent_name: str) -> str:
    return f"agent-result:{agent_name}"


def _project_findings(
    values: object,
    *,
    source_id: str,
) -> tuple[FindingExecutionEvidence, ...]:
    if not isinstance(values, list):
        return ()
    projected: list[FindingExecutionEvidence] = []
    for index, finding in enumerate(values, start=1):
        category = safe_optional_text(getattr(finding, "category", None))
        severity = safe_optional_text(getattr(finding, "severity", None))
        description = safe_optional_text(getattr(finding, "description", None))
        recommendation = safe_optional_text(
            getattr(finding, "recommendation", None)
        )
        if None in (category, severity, description, recommendation):
            continue
        identifier = safe_source_fragment(
            getattr(finding, "id", ""),
            fallback=f"finding-{index}",
        )
        projected.append(
            FindingExecutionEvidence(
                source_id=f"{source_id}#{identifier}",
                category=category,
                severity=severity,
                description=description,
                evidence=safe_text_items(getattr(finding, "evidence", [])),
                recommendation=recommendation,
            )
        )
    return tuple(projected)


def _project_domain_result(
    agent_name: str,
    source_id: str,
    result: object,
) -> DomainExecutionEvidence | object:
    if isinstance(result, FirmwareProject):
        return FirmwareExecutionEvidence(
            project_name=safe_optional_text(result.name),
            platform=safe_optional_text(result.platform),
            framework=safe_optional_text(result.framework),
            file_paths=tuple(
                file.path
                for file in result.files
                if is_safe_relative_path(file.path)
            ),
            structure=safe_text_items(result.structure),
        )
    if isinstance(result, HardwarePlan):
        return HardwareExecutionEvidence(
            project_name=safe_optional_text(result.project_name),
            platform=safe_optional_text(result.platform),
            mcu=safe_optional_text(result.mcu),
            components=tuple(
                name
                for component in result.components
                if (name := safe_optional_text(component.name)) is not None
            ),
            interfaces=safe_text_items(result.interfaces),
            power_requirements=safe_text_items(result.power_requirements),
            constraints=safe_text_items(result.constraints),
            rationale=safe_optional_text(result.rationale),
        )
    if isinstance(result, PCBReviewReport):
        return PCBExecutionEvidence(
            project_name=safe_optional_text(result.project_name),
            platform=safe_optional_text(result.platform),
            summary=safe_optional_text(result.summary),
            findings=_project_findings(result.issues, source_id=source_id),
            passed_rules=safe_text_items(result.passed_rules),
            warnings=safe_text_items(result.warnings),
        )
    if isinstance(result, DebugReport):
        recommendations = tuple(
            RecommendationExecutionEvidence(
                source_id=f"{source_id}#recommendation:{index}",
                text=text,
            )
            for index, value in enumerate(result.recommendations, start=1)
            if (text := safe_optional_text(value)) is not None
        )
        return DebugExecutionEvidence(
            project_name=safe_optional_text(result.project_name),
            platform=safe_optional_text(result.platform),
            error_type=safe_optional_text(result.error_type),
            summary=safe_optional_text(result.summary),
            findings=_project_findings(result.findings, source_id=source_id),
            recommendations=recommendations,
        )
    return result


class AgentExecutionResult(_IntegrationModel):
    agent_name: IntegrationAgentName
    source_id: str = Field(min_length=1, max_length=160)
    status: AgentStatus
    result: DomainExecutionEvidence | None = None

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> object:
        return _validate_safe_source_id(value)

    @model_validator(mode="before")
    @classmethod
    def project_result(cls, value: object) -> object:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        payload = copy.deepcopy(dict(value))
        agent_name = payload.get("agent_name")
        if not isinstance(agent_name, str):
            return payload
        source_id = payload.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            source_id = _agent_source_id(agent_name)
            payload["source_id"] = source_id
        payload["result"] = _project_domain_result(
            agent_name,
            source_id,
            payload.get("result"),
        )
        return payload

    @model_validator(mode="after")
    def validate_result_contract(self) -> "AgentExecutionResult":
        expected_types: dict[str, type[DomainExecutionEvidence]] = {
            "FirmwareAgent": FirmwareExecutionEvidence,
            "HardwareAgent": HardwareExecutionEvidence,
            "PCBAgent": PCBExecutionEvidence,
            "DebugAgent": DebugExecutionEvidence,
        }
        if self.status is AgentStatus.SUCCESS and self.result is None:
            raise ValueError("successful execution requires result")
        if self.status is AgentStatus.ERROR and self.result is not None:
            raise ValueError("failed execution must not contain result")
        if self.result is not None and not isinstance(
            self.result,
            expected_types[self.agent_name],
        ):
            raise ValueError("execution result does not match agent")
        return self


class EngineeringContext(_IntegrationModel):
    request: str = Field(min_length=1)
    input_context: UnifiedInputContext | None = None
    knowledge_context: IntegrationKnowledgeContext | None = None
    pcb_model: UnifiedPCBModel | None = None
    datasheet_model: UnifiedDatasheetModel | None = None
    agent_results: tuple[AgentExecutionResult, ...] = ()
    trace: tuple[IntegrationTraceEvent, ...] = ()

    @field_validator("request", mode="before")
    @classmethod
    def strip_request(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "input_context",
        "knowledge_context",
        "pcb_model",
        "datasheet_model",
        mode="before",
    )
    @classmethod
    def isolate_models(cls, value: object) -> object:
        if cls is EngineeringContext and value is not None:
            try:
                from embedded_copilot.supervisor.context import KnowledgeContext

                if isinstance(value, KnowledgeContext):
                    documents = tuple(
                        item
                        for item in value.retrieved_documents
                        if is_safe_report_text(item.id)
                        and is_safe_report_text(item.source.value)
                    )
                    return IntegrationKnowledgeContext(
                        source_ids=tuple(item.id for item in documents),
                        sources=tuple(item.source.value for item in documents),
                        result_count=len(documents),
                        summary=f"Retrieved {len(documents)} knowledge result(s).",
                    )
            except ImportError:
                pass
        return copy.deepcopy(value)

    @field_validator("agent_results", "trace", mode="before")
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return tuple(copy.deepcopy(value))
        return value

    @model_validator(mode="after")
    def validate_unique_agent_results(self) -> "EngineeringContext":
        names = [item.agent_name.casefold() for item in self.agent_results]
        if len(names) != len(set(names)):
            raise ValueError("engineering context contains duplicate agent results")
        source_ids = [item.source_id.casefold() for item in self.agent_results]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("engineering context contains duplicate source ids")
        sequences = [item.sequence for item in self.trace]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("engineering context trace sequence is invalid")
        return self
