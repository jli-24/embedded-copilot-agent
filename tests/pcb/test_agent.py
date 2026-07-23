import importlib.util

from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.pcb.knowledge import PCBKnowledgeRetriever, PCBRuleDocument
from embedded_copilot.pcb.models import (
    PCBReviewReport,
    PCBValidationResult,
)


def _document() -> PCBRuleDocument:
    return PCBRuleDocument(
        id="spi-rule",
        title="Authorized SPI Review Notes",
        category="communication",
        content="PRIVATE_DOCUMENT_SENTINEL SPI layout guidance",
        metadata={"license": "test"},
    )


def test_agent_runs_full_pipeline_and_returns_safe_metadata() -> None:
    result = PCBAgent(
        retriever=PCBKnowledgeRetriever([_document()])
    ).run(
        AgentTask(
            task_id="pcb-1",
            task_type="pcb",
            requirement="ESP32 camera SPI PCB review",
        )
    )

    report = PCBReviewReport.model_validate_json(result.output)
    serialized_metadata = str(result.metadata)
    assert result.status is AgentStatus.SUCCESS
    assert report.platform == "ESP32"
    assert result.metadata["pcb_review"] == report.model_dump(mode="json")
    assert result.metadata["retrieved_documents"] == [
        {
            "id": "spi-rule",
            "title": "Authorized SPI Review Notes",
            "category": "communication",
            "retrieval_score": 2,
        }
    ]
    assert result.metadata["validation"]["success"] is True
    assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized_metadata


def test_agent_accepts_hardware_plan_dict_from_metadata() -> None:
    plan = HardwarePlan(
        project_name="camera_board",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="Power stage",
                category="power",
                description="Unverified",
            )
        ],
        constraints=["Decoupling and GND integrity are declared."],
        rationale="Unverified",
    )
    result = PCBAgent().run(
        AgentTask(
            task_id="pcb-2",
            task_type="pcb",
            requirement="Review hardware plan",
            metadata={"hardware_plan": plan.model_dump(mode="json")},
        )
    )

    report = PCBReviewReport.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert report.project_name == "camera_board"
    assert report.issues == []


class _SearchOnlyRetriever:
    def search(self, query: str):
        return [_document()]

    def add_documents(self, documents):
        return None


class _RetrieveOnlyRetriever:
    def retrieve(self, query: str):
        return []


class _UnsafeScoreRetriever:
    def search(self, query: str):
        return [
            _document().model_copy(
                update={
                    "metadata": {
                        "retrieval_score": (
                            "C:/Users/secret/score PRIVATE_DOCUMENT_SENTINEL"
                        )
                    }
                }
            )
        ]


def test_agent_supports_search_only_and_retrieve_only_retrievers() -> None:
    task = AgentTask(task_id="pcb-3", task_type="pcb", requirement="ESP32 SPI")

    search_result = PCBAgent(retriever=_SearchOnlyRetriever()).run(task)
    retrieve_result = PCBAgent(retriever=_RetrieveOnlyRetriever()).run(task)

    assert search_result.status is AgentStatus.SUCCESS
    assert retrieve_result.status is AgentStatus.SUCCESS


def test_agent_only_exposes_numeric_retrieval_scores() -> None:
    result = PCBAgent(retriever=_UnsafeScoreRetriever()).run(
        AgentTask(task_id="pcb-score", task_type="pcb", requirement="ESP32 SPI")
    )

    serialized = f"{result.output} {result.metadata}"
    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"][0]["retrieval_score"] is None
    assert "C:/Users" not in serialized
    assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized


class _RejectingValidator:
    def validate(self, report):
        return PCBValidationResult(
            success=False,
            errors=["private C:/Users/secret PRIVATE_DOCUMENT_SENTINEL"],
        )


def test_agent_redacts_rejected_report_and_validation_details() -> None:
    result = PCBAgent(
        retriever=PCBKnowledgeRetriever([_document()]),
        validator=_RejectingValidator(),
    ).run(
        AgentTask(
            task_id="pcb-4",
            task_type="pcb",
            requirement="ESP32 SPI",
        )
    )

    serialized = f"{result.output} {result.metadata}"
    assert result.status is AgentStatus.ERROR
    assert result.output == "PCB review validation failed"
    assert "C:/Users" not in serialized
    assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized


class _UnexpectedAnalyzerFailure:
    def analyze(self, source, *, metadata=None):
        raise RuntimeError("private C:/Users/secret/analysis PRIVATE_DOCUMENT_SENTINEL")


class _UnexpectedRetrieverFailure:
    def search(self, query):
        raise RuntimeError("private C:/Users/secret/knowledge PRIVATE_DOCUMENT_SENTINEL")


class _UnexpectedRuleFailure:
    def evaluate(self, requirement):
        raise RuntimeError("private C:/Users/secret/rule PRIVATE_DOCUMENT_SENTINEL")


class _UnexpectedReviewerFailure:
    def review(self, requirement, documents, *, evaluation=None):
        raise RuntimeError("private C:/Users/secret/review PRIVATE_DOCUMENT_SENTINEL")


class _UnexpectedValidatorFailure:
    def validate(self, report):
        raise RuntimeError("private C:/Users/secret/validation PRIVATE_DOCUMENT_SENTINEL")


def test_agent_maps_unexpected_stage_failures_to_safe_classifications() -> None:
    task = AgentTask(task_id="pcb-5", task_type="pcb", requirement="ESP32 SPI")
    cases = (
        (
            PCBAgent(analyzer=_UnexpectedAnalyzerFailure()),
            "PCB requirement analysis failed",
            "PCBAnalysisError",
        ),
        (
            PCBAgent(retriever=_UnexpectedRetrieverFailure()),
            "PCB knowledge retrieval failed",
            "PCBKnowledgeError",
        ),
        (
            PCBAgent(rule_engine=_UnexpectedRuleFailure()),
            "PCB rule evaluation failed",
            "PCBRuleError",
        ),
        (
            PCBAgent(reviewer=_UnexpectedReviewerFailure()),
            "PCB review failed",
            "PCBReviewError",
        ),
        (
            PCBAgent(validator=_UnexpectedValidatorFailure()),
            "PCB review validation failed",
            "PCBValidationError",
        ),
    )

    for agent, expected_output, expected_error_type in cases:
        result = agent.run(task)
        serialized = f"{result.output} {result.metadata}"
        assert result.status is AgentStatus.ERROR
        assert result.output == expected_output
        assert result.metadata["error_type"] == expected_error_type
        assert "C:/Users" not in serialized
        assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized


class _MalformedAnalyzer:
    def analyze(self, source, *, metadata=None):
        return {"private": "C:/Users/secret/analysis PRIVATE_DOCUMENT_SENTINEL"}


class _MalformedRetriever:
    def search(self, query):
        return [object()]


class _MalformedRuleEngine:
    def evaluate(self, requirement):
        return object()


class _MalformedReviewer:
    def review(self, requirement, documents, *, evaluation=None):
        return object()


class _MalformedValidator:
    def validate(self, report):
        return object()


def test_agent_rejects_malformed_stage_outputs_with_safe_classifications() -> None:
    task = AgentTask(task_id="pcb-6", task_type="pcb", requirement="ESP32 SPI")
    cases = (
        (PCBAgent(analyzer=_MalformedAnalyzer()), "PCBAnalysisError"),
        (PCBAgent(retriever=_MalformedRetriever()), "PCBKnowledgeError"),
        (PCBAgent(rule_engine=_MalformedRuleEngine()), "PCBRuleError"),
        (PCBAgent(reviewer=_MalformedReviewer()), "PCBReviewError"),
        (PCBAgent(validator=_MalformedValidator()), "PCBValidationError"),
    )

    for agent, expected_error_type in cases:
        result = agent.run(task)
        serialized = f"{result.output} {result.metadata}"
        assert result.status is AgentStatus.ERROR
        assert result.metadata["error_type"] == expected_error_type
        assert "C:/Users" not in serialized
        assert "PRIVATE_DOCUMENT_SENTINEL" not in serialized


def test_agent_rejects_invalid_hardware_plan_payload_safely() -> None:
    result = PCBAgent().run(
        AgentTask(
            task_id="pcb-7",
            task_type="pcb",
            requirement="Review hardware plan",
            metadata={"hardware_plan": {"project_name": "missing fields"}},
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "PCB requirement analysis failed"


def test_foundation_pcb_agent_does_not_create_runtime_agent() -> None:
    from embedded_copilot.pcb import PCBAgent as PublicPCBAgent

    assert PublicPCBAgent is PCBAgent
    assert importlib.util.find_spec("embedded_copilot.agents.pcb") is None
