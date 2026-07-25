from __future__ import annotations

import copy

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentResult, AgentStatus, AgentTask
from embedded_copilot.datasheet.adapters import to_hardware_document
from embedded_copilot.datasheet.models import DatasheetElectricalSpec, UnifiedDatasheetModel
from embedded_copilot.engineering.crosscheck import (
    EngineeringCrossCheckFinding,
    cross_check,
)
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.firmware.review.project_adapter import FirmwareReviewProjectAdapter
from embedded_copilot.hardware.models import HardwarePlan
from embedded_copilot.hardware.validator import HardwareValidator


_ENVELOPE_KEY = "_real_engineering_input"


class ExtensionMetadataSanitizingAgentAdapter(BaseAgent):
    """Remove extension-private metadata before delegating exactly once."""

    def __init__(self, delegate: BaseAgent) -> None:
        self._delegate = delegate
        self.name = delegate.name
        self.description = delegate.description
        self.capabilities = delegate.capabilities

    def run(self, task: AgentTask) -> AgentResult:
        if not isinstance(task, AgentTask):
            return self._delegate.run(task)
        metadata = copy.deepcopy(task.metadata)
        metadata.pop(_ENVELOPE_KEY, None)
        clean_task = task.model_copy(update={"metadata": metadata}, deep=True)
        return self._delegate.run(clean_task)


class FirmwareAgentInputAdapter(BaseAgent):
    def __init__(self, delegate: BaseAgent) -> None:
        self._delegate = delegate
        self.name = delegate.name
        self.description = delegate.description
        self.capabilities = delegate.capabilities
        self._project_adapter = FirmwareReviewProjectAdapter()

    def run(self, task: AgentTask) -> AgentResult:
        clean_task, envelope = _consume_envelope(task)
        if envelope is None:
            return self._delegate.run(clean_task)
        error = _domain_error(envelope, "firmware")
        if error is not None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output="firmware source review failed",
                metadata={"error_type": error.code},
            )
        if envelope.firmware_review is None:
            return self._delegate.run(clean_task)
        project = self._project_adapter.to_project(envelope.firmware_review)
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=project.model_dump_json(),
            metadata={
                "firmware_project": project.model_dump(mode="json"),
                "review": {
                    "analysis_mode": "deterministic_static_review",
                    "finding_count": len(envelope.firmware_review.findings),
                    "source_ids": list(envelope.firmware_review.source_ids),
                },
            },
        )


class HardwareAgentInputAdapter(BaseAgent):
    def __init__(self, delegate: BaseAgent) -> None:
        self._delegate = delegate
        self.name = delegate.name
        self.description = delegate.description
        self.capabilities = delegate.capabilities
        self._validator = HardwareValidator()

    def run(self, task: AgentTask) -> AgentResult:
        clean_task, envelope = _consume_envelope(task)
        if envelope is None:
            return self._delegate.run(clean_task)
        error = _domain_error(envelope, "datasheet")
        if error is not None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output="datasheet engineering analysis failed",
                metadata={"error_type": error.code},
            )
        if envelope.datasheet is None:
            return self._delegate.run(clean_task)
        findings = (
            cross_check(envelope.datasheet, envelope.firmware_review)
            if envelope.firmware_review is not None
            else ()
        )
        delegated_task = _hardware_task(clean_task, envelope.datasheet, findings)
        delegated_result = self._delegate.run(delegated_task)
        if delegated_result.status is AgentStatus.ERROR:
            return delegated_result
        try:
            plan = HardwarePlan.model_validate_json(delegated_result.output)
            projected = _project_hardware_plan(plan, envelope.datasheet, findings)
            validation = self._validator.validate(projected)
            if not validation.success:
                raise ValueError("invalid projected plan")
        except Exception:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                output="hardware evidence projection failed",
                metadata={"error_type": "HardwareProjectionError"},
            )
        metadata = copy.deepcopy(delegated_result.metadata)
        metadata["real_engineering"] = {
            "datasheet_source_id": envelope.datasheet.metadata.get("source_id"),
            "crosscheck_finding_count": len(findings),
        }
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            output=projected.model_dump_json(),
            metadata=metadata,
        )


def _consume_envelope(
    task: AgentTask,
) -> tuple[AgentTask, RealEngineeringEnvelope | None]:
    if not isinstance(task, AgentTask):
        raise TypeError("engineering Agent adapter task is invalid")
    metadata = copy.deepcopy(task.metadata)
    raw = metadata.pop(_ENVELOPE_KEY, None)
    clean = task.model_copy(update={"metadata": metadata}, deep=True)
    if raw is None:
        return clean, None
    return clean, RealEngineeringEnvelope.model_validate(raw)


def _domain_error(envelope: RealEngineeringEnvelope, domain: str):
    return next((item for item in envelope.errors if item.domain == domain), None)


def _hardware_task(
    task: AgentTask,
    datasheet: UnifiedDatasheetModel,
    findings: tuple[EngineeringCrossCheckFinding, ...],
) -> AgentTask:
    document = to_hardware_document(datasheet)
    metadata = copy.deepcopy(task.metadata)
    documents = metadata.get("knowledge_documents", [])
    provenance = metadata.get("knowledge_provenance", [])
    if not isinstance(documents, list) or not isinstance(provenance, list):
        raise TypeError("hardware knowledge metadata is invalid")
    metadata["knowledge_mode"] = "supervisor_gateway"
    metadata["knowledge_documents"] = [
        *copy.deepcopy(documents),
        document.model_dump(mode="json"),
    ]
    metadata["knowledge_provenance"] = [
        *copy.deepcopy(provenance),
        {
            "id": document.id,
            "title": document.title,
            "source": "attachment",
            "category": document.category,
            "score": None,
        },
    ]
    metadata["mcu"] = datasheet.component.part_number
    metadata["platform"] = _platform(datasheet.component.part_number)
    metadata["peripherals"] = _peripherals(datasheet)
    metadata["interfaces"] = _interfaces(datasheet)
    existing_constraints = metadata.get("constraints", [])
    if not isinstance(existing_constraints, list):
        raise TypeError("hardware constraints metadata is invalid")
    metadata["constraints"] = [
        *copy.deepcopy(existing_constraints),
        *(_finding_text(item) for item in findings),
    ]
    return task.model_copy(update={"metadata": metadata}, deep=True)


def _project_hardware_plan(
    plan: HardwarePlan,
    datasheet: UnifiedDatasheetModel,
    findings: tuple[EngineeringCrossCheckFinding, ...],
) -> HardwarePlan:
    payload = plan.model_dump(mode="python")
    payload["mcu"] = datasheet.component.part_number
    payload["interfaces"] = list(
        dict.fromkeys([*plan.interfaces, *_interfaces(datasheet)])
    )
    power = [_electrical_text(item) for item in datasheet.power_requirements]
    payload["power_requirements"] = list(
        dict.fromkeys([*power, *plan.power_requirements])
    )
    payload["constraints"] = list(
        dict.fromkeys([*plan.constraints, *(_finding_text(item) for item in findings)])
    )
    payload["rationale"] = (
        f"{plan.rationale} Text-layer Datasheet evidence was applied from "
        f"{datasheet.metadata.get('source_id', 'attachment:datasheet')}."
    )
    metadata = copy.deepcopy(plan.metadata)
    metadata["real_engineering"] = True
    metadata["datasheet_source_id"] = datasheet.metadata.get("source_id")
    payload["metadata"] = metadata
    return HardwarePlan.model_validate(payload)


def _interfaces(datasheet: UnifiedDatasheetModel) -> list[str]:
    allowed = {"GPIO", "UART", "SPI", "I2C", "ADC", "WiFi", "Bluetooth", "USB"}
    values = [item.protocol for item in datasheet.interfaces if item.protocol in allowed]
    if datasheet.pins:
        values.append("GPIO")
    return list(dict.fromkeys(values))


def _peripherals(datasheet: UnifiedDatasheetModel) -> list[str]:
    values = [
        "Camera" if item.protocol == "Camera" else item.protocol
        for item in datasheet.interfaces
        if item.protocol in {"Camera", "UART", "SPI", "I2C"}
    ]
    return list(dict.fromkeys(values))


def _platform(part_number: str) -> str:
    normalized = part_number.casefold()
    if normalized.startswith("esp32"):
        return "ESP32"
    if normalized.startswith("stm32"):
        return "STM32"
    return part_number


def _electrical_text(specification: DatasheetElectricalSpec) -> str:
    values = [
        value
        for value in (
            specification.min_value,
            specification.typical_value,
            specification.max_value,
        )
        if value is not None
    ]
    rendered = " to ".join(f"{value:g}" for value in (values[0], values[-1]))
    return f"{specification.parameter}: {rendered} {specification.unit}"


def _finding_text(finding: EngineeringCrossCheckFinding) -> str:
    return (
        f"[{finding.severity.upper()}] {finding.rule_id}: {finding.description} "
        f"Recommendation: {finding.recommendation} "
        f"[source_id: {', '.join(finding.source_ids)}]"
    )
