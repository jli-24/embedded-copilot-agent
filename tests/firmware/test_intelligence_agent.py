from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.exceptions import FirmwarePlanningError
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.knowledge.retriever import FirmwareKnowledgeRetriever
from embedded_copilot.firmware.models import GeneratedCode, GeneratedFile, ValidationResult
from embedded_copilot.firmware.planner.models import FirmwarePlan


def _document() -> FirmwareDocument:
    return FirmwareDocument(
        id="camera-doc",
        title="Camera Guide",
        platform="ESP32",
        framework="ESP-IDF",
        content="ESP32 WiFi Camera guidance",
        metadata={"source": "camera.md"},
    )


def test_agent_runs_intelligence_pipeline_and_returns_metadata() -> None:
    agent = FirmwareAgent(
        retriever=FirmwareKnowledgeRetriever([_document()]),
    )

    result = agent.run(
        AgentTask(
            task_id="intel-1",
            task_type="firmware",
            requirement="ESP32-S3 ESP-IDF WiFi Camera",
        )
    )

    generated = GeneratedCode.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert [item.filename for item in generated.files] == [
        "main.c",
        "wifi.c",
        "camera.c",
    ]
    assert result.metadata["firmware_plan"]["components"] == ["wifi", "camera"]
    assert result.metadata["retrieved_documents"][0]["id"] == "camera-doc"
    assert result.metadata["validation"]["success"] is True


def test_agent_uses_rule_plan_when_retrieval_is_empty() -> None:
    result = FirmwareAgent().run(
        AgentTask(
            task_id="intel-2",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"] == []
    assert "unverified" in result.metadata["firmware_plan"]["rationale"]


class _TrackingAnalyzer:
    def __init__(self) -> None:
        self.called = False

    def analyze(self, requirement: str, *, metadata=None):
        from embedded_copilot.firmware.intelligence.analyzer import (
            FirmwareRequirementAnalysis,
        )

        self.called = True
        return FirmwareRequirementAnalysis(
            requirement=requirement,
            platform="ESP32",
            framework="ESP-IDF",
            features=["gpio"],
            peripherals=["GPIO"],
            metadata=dict(metadata or {}),
        )


class _TrackingRetriever:
    def __init__(self) -> None:
        self.called = False

    def retrieve(self, query: str):
        self.called = True
        return []


class _SearchOnlyRetriever:
    def search(self, query: str):
        return [_document()]

    def add_documents(self, documents):
        return None


class _TrackingPlanner:
    def __init__(self) -> None:
        self.called = False

    def plan(self, analysis, documents):
        self.called = True
        return FirmwarePlan(
            platform="ESP32",
            framework="ESP-IDF",
            components=["gpio"],
            peripherals=["GPIO"],
            files=["main.c"],
            dependencies=["ESP-IDF"],
            rationale="test plan",
        )


class _TrackingGenerator:
    def __init__(self) -> None:
        self.called = False

    def generate(self, request):
        self.called = True
        return GeneratedCode(
            project_name="test",
            platform="ESP32",
            files=[GeneratedFile(filename="main.c", content="mock", language="C")],
        )


class _TrackingValidator:
    def __init__(self) -> None:
        self.called = False

    def validate(self, generated):
        self.called = True
        return ValidationResult(success=True)


def test_agent_invokes_every_injected_stage() -> None:
    analyzer = _TrackingAnalyzer()
    retriever = _TrackingRetriever()
    planner = _TrackingPlanner()
    generator = _TrackingGenerator()
    validator = _TrackingValidator()
    agent = FirmwareAgent(
        analyzer=analyzer,
        retriever=retriever,
        planner=planner,
        generator=generator,
        validator=validator,
    )

    result = agent.run(
        AgentTask(task_id="intel-3", task_type="firmware", requirement="test")
    )

    assert result.status is AgentStatus.SUCCESS
    assert all(
        stage.called for stage in (analyzer, retriever, planner, generator, validator)
    )


class _FailingPlanner:
    def plan(self, analysis, documents):
        raise FirmwarePlanningError("private C:\\Users\\secret\\document")


def test_agent_does_not_expose_raw_intelligence_exception() -> None:
    result = FirmwareAgent(planner=_FailingPlanner()).run(
        AgentTask(
            task_id="intel-4",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.metadata["error_type"] == "FirmwarePlanningError"
    assert "private" not in result.output
    assert "Users" not in result.output


def test_agent_filters_retrieved_documents_by_platform_and_framework() -> None:
    esp32_document = _document()
    stm32_document = FirmwareDocument(
        id="stm32-doc",
        title="STM32 WiFi Notes",
        platform="STM32",
        framework="HAL",
        content="WiFi guidance",
        metadata={"source": "stm32.md"},
    )
    agent = FirmwareAgent(
        retriever=FirmwareKnowledgeRetriever([stm32_document, esp32_document])
    )

    result = agent.run(
        AgentTask(
            task_id="intel-5",
            task_type="firmware",
            requirement="ESP32 ESP-IDF WiFi",
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert [
        document["id"] for document in result.metadata["retrieved_documents"]
    ] == ["camera-doc"]


def test_agent_accepts_search_only_knowledge_retriever_protocol() -> None:
    result = FirmwareAgent(retriever=_SearchOnlyRetriever()).run(
        AgentTask(
            task_id="intel-6",
            task_type="firmware",
            requirement="ESP32 ESP-IDF WiFi",
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"][0]["id"] == "camera-doc"
