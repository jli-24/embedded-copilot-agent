from __future__ import annotations

from collections.abc import Callable

import pytest

from embedded_copilot.agents.base import BaseAgent
from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.debug.agent import DebugAgent
from embedded_copilot.debug.models import DebugEvidence
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument


class FailingRetriever:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: object) -> object:
        self.calls += 1
        raise AssertionError("local retriever must not be called")

    def retrieve(self, query: object) -> object:
        self.calls += 1
        raise AssertionError("local retriever must not be called")


AgentFactory = Callable[[object], BaseAgent]


@pytest.mark.parametrize(
    ("agent_factory", "requirement", "field"),
    [
        (
            lambda retriever: FirmwareAgent(retriever=retriever),
            "Generate an ESP32 ESP-IDF GPIO firmware project",
            "knowledge_documents",
        ),
        (
            lambda retriever: HardwareAgent(retriever=retriever),
            "Plan ESP32 hardware with an I2C sensor",
            "knowledge_documents",
        ),
        (
            lambda retriever: PCBAgent(retriever=retriever),
            "Review ESP32 PCB power and decoupling",
            "knowledge_documents",
        ),
        (
            lambda retriever: DebugAgent(retriever=retriever),
            "ESP32 compiler error undefined reference to camera_init",
            "knowledge_evidence",
        ),
    ],
)
def test_centralized_empty_knowledge_never_falls_back_to_local_retriever(
    agent_factory: AgentFactory,
    requirement: str,
    field: str,
) -> None:
    agent = agent_factory(FailingRetriever())
    result = agent.run(
        AgentTask(
            task_id="centralized-empty",
            task_type=agent.name,
            requirement=requirement,
            metadata={
                "knowledge_mode": "supervisor_gateway",
                field: [],
                "knowledge_provenance": [],
            },
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"] == []


@pytest.mark.parametrize(
    ("agent", "requirement", "field", "document"),
    [
        (
            FirmwareAgent(retriever=FailingRetriever()),
            "Generate an ESP32 ESP-IDF GPIO firmware project",
            "knowledge_documents",
            FirmwareDocument(
                id="firmware-doc",
                title="Firmware document",
                platform="ESP32",
                framework="ESP-IDF",
                content="PRIVATE_CENTRALIZED_KNOWLEDGE",
            ),
        ),
        (
            HardwareAgent(retriever=FailingRetriever()),
            "Plan ESP32 hardware with an I2C sensor",
            "knowledge_documents",
            HardwareDocument(
                id="hardware-doc",
                title="Hardware document",
                category="sensor",
                vendor="Synthetic",
                content="PRIVATE_CENTRALIZED_KNOWLEDGE",
            ),
        ),
        (
            PCBAgent(retriever=FailingRetriever()),
            "Review ESP32 PCB power and decoupling",
            "knowledge_documents",
            PCBRuleDocument(
                id="pcb-doc",
                title="PCB document",
                category="power",
                content="PRIVATE_CENTRALIZED_KNOWLEDGE",
            ),
        ),
        (
            DebugAgent(retriever=FailingRetriever()),
            "ESP32 compiler error undefined reference to camera_init",
            "knowledge_evidence",
            DebugEvidence(
                source="LOCAL:debug-doc",
                content="PRIVATE_CENTRALIZED_KNOWLEDGE",
                category="compile",
                metadata={
                    "id": "debug-doc",
                    "title": "Debug document",
                    "source": "LOCAL",
                    "score": 0.7,
                },
            ),
        ),
    ],
)
def test_centralized_agents_consume_validated_domain_input_and_expose_provenance(
    agent: BaseAgent,
    requirement: str,
    field: str,
    document: object,
) -> None:
    provenance = [
        {
            "id": "safe-id",
            "title": "Safe title",
            "source": "LOCAL",
            "category": "general",
            "score": 0.7,
        }
    ]
    result = agent.run(
        AgentTask(
            task_id="centralized-document",
            task_type=agent.name,
            requirement=requirement,
            metadata={
                "knowledge_mode": "supervisor_gateway",
                field: [document.model_dump(mode="json")],  # type: ignore[attr-defined]
                "knowledge_provenance": provenance,
            },
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"] == provenance
    assert "PRIVATE_CENTRALIZED_KNOWLEDGE" not in str(result.metadata)


@pytest.mark.parametrize(
    ("agent", "requirement", "field", "expected_output"),
    [
        (
            FirmwareAgent(retriever=FailingRetriever()),
            "Generate an ESP32 ESP-IDF GPIO firmware project",
            "knowledge_documents",
            "firmware knowledge retrieval failed",
        ),
        (
            HardwareAgent(retriever=FailingRetriever()),
            "Plan ESP32 hardware with an I2C sensor",
            "knowledge_documents",
            "hardware knowledge retrieval failed",
        ),
        (
            PCBAgent(retriever=FailingRetriever()),
            "Review ESP32 PCB power and decoupling",
            "knowledge_documents",
            "PCB knowledge retrieval failed",
        ),
        (
            DebugAgent(retriever=FailingRetriever()),
            "ESP32 compiler error undefined reference to camera_init",
            "knowledge_evidence",
            "debug knowledge retrieval failed",
        ),
    ],
)
def test_centralized_agents_reject_malformed_domain_input_without_fallback(
    agent: BaseAgent,
    requirement: str,
    field: str,
    expected_output: str,
) -> None:
    result = agent.run(
        AgentTask(
            task_id="centralized-malformed",
            task_type=agent.name,
            requirement=requirement,
            metadata={
                "knowledge_mode": "supervisor_gateway",
                field: [{"malformed": True}],
                "knowledge_provenance": [],
            },
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == expected_output
    assert agent._retriever.calls == 0  # type: ignore[attr-defined]  # noqa: SLF001
