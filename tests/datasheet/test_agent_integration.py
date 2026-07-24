from __future__ import annotations

from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.datasheet.adapters import (
    to_firmware_document,
    to_hardware_document,
    to_pcb_rule_document,
)
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.knowledge.retriever import HardwareKnowledgeRetriever
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever

from tests.datasheet.test_adapters import _payload


def _task(task_type: str, requirement: str) -> AgentTask:
    return AgentTask(
        task_id=f"datasheet:{task_type}",
        task_type=task_type,
        requirement=requirement,
    )


def test_hardware_agent_uses_datasheet_document_through_existing_retriever() -> None:
    model = UnifiedDatasheetModel.model_validate(_payload())
    document = to_hardware_document(model)
    agent = HardwareAgent(retriever=HardwareKnowledgeRetriever([document]))

    result = agent.run(_task("hardware", "Design ESP32-S3 UART hardware"))

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"][0]["id"] == document.id
    assert result.metadata["hardware_plan"]["metadata"][
        "evidence_document_ids"
    ] == [document.id]


def test_pcb_agent_uses_datasheet_document_through_existing_retriever() -> None:
    model = UnifiedDatasheetModel.model_validate(_payload())
    document = to_pcb_rule_document(model)
    agent = PCBAgent(retriever=PCBKnowledgeRetriever([document]))

    result = agent.run(_task("pcb", "Review ESP32 UART power PCB constraints"))

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"][0]["id"] == document.id
    assert result.metadata["pcb_review"]["metadata"]["evidence_document_ids"] == [
        document.id
    ]


def test_firmware_agent_uses_datasheet_document_through_existing_retriever() -> None:
    model = UnifiedDatasheetModel.model_validate(_payload("STM32F407VG"))
    document = to_firmware_document(model)
    agent = FirmwareAgent(retriever=FirmwareKnowledgeRetriever([document]))

    result = agent.run(_task("firmware", "Create STM32 HAL UART firmware"))

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"][0]["id"] == document.id
    assert document.id in result.metadata["firmware_plan"]["rationale"]


def test_agents_preserve_legacy_behavior_without_datasheet_documents() -> None:
    results = (
        HardwareAgent().run(_task("hardware", "Design ESP32 UART hardware")),
        PCBAgent().run(_task("pcb", "Review ESP32 UART PCB")),
        FirmwareAgent().run(_task("firmware", "Create STM32 HAL UART firmware")),
    )

    assert all(result.status is AgentStatus.SUCCESS for result in results)
    assert all(result.metadata["retrieved_documents"] == [] for result in results)
