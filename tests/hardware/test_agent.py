from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.firmware.project.models import FirmwareProject
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.hardware.exceptions import HardwarePlanningError
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.hardware.models import HardwarePlan, HardwareValidationResult


def _document() -> HardwareDocument:
    return HardwareDocument(
        id="camera-doc",
        title="Camera Guide",
        category="camera",
        vendor="Example",
        content="ESP32-S3 camera selection",
        metadata={"peripheral": "Camera", "component_name": "OV2640 camera"},
    )


def test_agent_runs_hardware_pipeline_and_returns_metadata() -> None:
    from embedded_copilot.hardware.knowledge.retriever import (
        HardwareKnowledgeRetriever,
    )

    result = HardwareAgent(
        retriever=HardwareKnowledgeRetriever([_document()])
    ).run(
        AgentTask(
            task_id="hardware-1",
            task_type="hardware",
            requirement="ESP32-S3 camera",
        )
    )

    plan = HardwarePlan.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert plan.components[0].name == "OV2640 camera"
    assert result.metadata["hardware_plan"] == plan.model_dump(mode="json")
    assert result.metadata["retrieved_documents"][0]["id"] == "camera-doc"
    assert result.metadata["validation"]["success"] is True


def test_agent_accepts_firmware_project_dict_from_metadata() -> None:
    project = FirmwareProject(
        name="camera_project",
        platform="ESP32",
        metadata={"peripherals": ["Camera"]},
    )
    result = HardwareAgent().run(
        AgentTask(
            task_id="hardware-2",
            task_type="hardware",
            requirement="Plan hardware from firmware project",
            metadata={"firmware_project": project.model_dump(mode="json")},
        )
    )

    plan = HardwarePlan.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert plan.project_name == "camera_project"
    assert plan.mcu == "ESP32"


class _SearchOnlyRetriever:
    def search(self, query: str):
        return [_document()]

    def add_documents(self, documents):
        return None


class _RetrieveOnlyRetriever:
    def retrieve(self, query: str):
        return []


def test_agent_supports_search_only_and_retrieve_only_retrievers() -> None:
    search_result = HardwareAgent(retriever=_SearchOnlyRetriever()).run(
        AgentTask(
            task_id="hardware-3",
            task_type="hardware",
            requirement="ESP32-S3 camera",
        )
    )
    retrieve_result = HardwareAgent(retriever=_RetrieveOnlyRetriever()).run(
        AgentTask(
            task_id="hardware-4",
            task_type="hardware",
            requirement="STM32 UART",
        )
    )

    assert search_result.status is AgentStatus.SUCCESS
    assert retrieve_result.status is AgentStatus.SUCCESS


class _FailingPlanner:
    def plan(self, requirement, documents):
        raise HardwarePlanningError("private C:\\Users\\secret\\hardware")


def test_agent_maps_internal_errors_to_safe_classification() -> None:
    result = HardwareAgent(planner=_FailingPlanner()).run(
        AgentTask(
            task_id="hardware-5",
            task_type="hardware",
            requirement="ESP32 camera",
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "hardware planning failed"
    assert result.metadata["error_type"] == "HardwarePlanningError"
    assert "Users" not in result.output


class _UnsafePlanner:
    def plan(self, requirement, documents):
        return HardwarePlan(
            project_name="C:/Users/private/project",
            platform="ESP32",
            mcu="ESP32",
            rationale="private internal rationale",
        )


class _RejectingValidator:
    def validate(self, plan):
        return HardwareValidationResult(
            success=False,
            errors=["private C:/Users/private/component"],
        )


def test_agent_redacts_rejected_plan_and_validation_details() -> None:
    result = HardwareAgent(
        planner=_UnsafePlanner(),
        validator=_RejectingValidator(),
    ).run(
        AgentTask(
            task_id="hardware-6",
            task_type="hardware",
            requirement="ESP32 camera",
        )
    )

    serialized = f"{result.output} {result.metadata}"
    assert result.status is AgentStatus.ERROR
    assert result.output == "hardware plan validation failed"
    assert "C:/Users" not in serialized
    assert "private internal rationale" not in serialized


def test_agent_rejects_invalid_firmware_project_payload_safely() -> None:
    result = HardwareAgent().run(
        AgentTask(
            task_id="hardware-7",
            task_type="hardware",
            requirement="Plan hardware",
            metadata={"firmware_project": {"name": "missing platform"}},
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "hardware requirement analysis failed"


class _UnexpectedAnalyzerFailure:
    def analyze(self, source, *, metadata=None):
        raise RuntimeError("private C:/Users/secret/analysis SENTINEL_DOCUMENT")


class _UnexpectedRetrieverFailure:
    def search(self, query):
        raise RuntimeError("private C:/Users/secret/knowledge SENTINEL_DOCUMENT")


class _UnexpectedPlannerFailure:
    def plan(self, requirement, documents):
        raise RuntimeError("private C:/Users/secret/planning SENTINEL_DOCUMENT")


class _UnexpectedValidatorFailure:
    def validate(self, plan):
        raise RuntimeError("private C:/Users/secret/validation SENTINEL_DOCUMENT")


def test_agent_maps_unexpected_stage_failures_to_safe_classifications() -> None:
    task = AgentTask(
        task_id="hardware-8",
        task_type="hardware",
        requirement="ESP32 camera",
    )
    cases = (
        (
            HardwareAgent(analyzer=_UnexpectedAnalyzerFailure()),
            "hardware requirement analysis failed",
            "HardwareAnalysisError",
        ),
        (
            HardwareAgent(retriever=_UnexpectedRetrieverFailure()),
            "hardware knowledge retrieval failed",
            "HardwareKnowledgeError",
        ),
        (
            HardwareAgent(planner=_UnexpectedPlannerFailure()),
            "hardware planning failed",
            "HardwarePlanningError",
        ),
        (
            HardwareAgent(validator=_UnexpectedValidatorFailure()),
            "hardware plan validation failed",
            "HardwareValidationError",
        ),
    )

    for agent, expected_output, expected_error_type in cases:
        result = agent.run(task)
        serialized = f"{result.output} {result.metadata}"
        assert result.status is AgentStatus.ERROR
        assert result.output == expected_output
        assert result.metadata["error_type"] == expected_error_type
        assert "C:/Users" not in serialized
        assert "SENTINEL_DOCUMENT" not in serialized
