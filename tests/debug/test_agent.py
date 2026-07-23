from __future__ import annotations

import inspect

import pytest

from embedded_copilot.agents.debug import DebugAgent as RuntimeDebugAgent
from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.debug import DebugAgent as PublicDebugAgent
from embedded_copilot.debug.agent import DebugAgent
from embedded_copilot.debug.models import DebugReport
from embedded_copilot.knowledge.gateway import KnowledgeGatewayAdapter
from embedded_copilot.knowledge.models import KnowledgeResult, KnowledgeSource


def _task(**metadata: object) -> AgentTask:
    return AgentTask(
        task_id="debug-1",
        task_type="debug",
        requirement="ESP32 task watchdog reset PRIVATE_FULL_LOG_SENTINEL",
        metadata=metadata,
    )


def test_debug_agent_import_paths_do_not_shadow_runtime_agent() -> None:
    assert PublicDebugAgent is DebugAgent
    assert DebugAgent is not RuntimeDebugAgent
    assert not inspect.iscoroutinefunction(DebugAgent.run)
    assert inspect.iscoroutinefunction(RuntimeDebugAgent.run)


def test_debug_agent_runs_complete_pipeline_without_knowledge() -> None:
    result = DebugAgent().run(_task(project_name="demo"))

    report = DebugReport.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert report.project_name == "demo"
    assert report.platform == "ESP32"
    assert [finding.id for finding in report.findings] == [
        "runtime_watchdog",
        "runtime_reset",
    ]
    assert report.metadata["analysis_mode"] == "unverified_rule_based"
    assert result.metadata["debug_report"] == report.model_dump(mode="json")
    assert result.metadata["retrieved_documents"] == []
    assert result.metadata["validation"]["success"] is True


def test_debug_agent_accepts_gateway_adapter_as_explicit_backend() -> None:
    class Gateway:
        def search(self, query):
            assert query.query == "ESP32 runtime_crash reset watchdog"
            return [
                KnowledgeResult(
                    id="watchdog",
                    title="Watchdog",
                    content="PRIVATE_KNOWLEDGE_BODY",
                    source=KnowledgeSource.LOCAL,
                    metadata={"category": "runtime"},
                )
            ]

    from embedded_copilot.debug.knowledge import DebugKnowledgeRetriever

    result = DebugAgent(
        retriever=DebugKnowledgeRetriever(
            KnowledgeGatewayAdapter(Gateway(), object())  # type: ignore[arg-type]
        )
    ).run(_task())

    assert result.status is AgentStatus.SUCCESS
    assert result.metadata["retrieved_documents"] == [
        {
            "id": "watchdog",
            "title": "Watchdog",
            "source": "LOCAL",
            "category": "runtime",
            "score": None,
        }
    ]
    assert "PRIVATE_KNOWLEDGE_BODY" not in str(result.metadata)


def test_debug_agent_deep_copies_task_metadata() -> None:
    nested = {"flag": True}

    class MutatingAnalyzer:
        def analyze(self, source: str, *, metadata: dict[str, object]):
            metadata["nested"]["flag"] = False  # type: ignore[index]
            from embedded_copilot.debug.analyzer import DebugRequirementAnalyzer

            return DebugRequirementAnalyzer().analyze(source, metadata=metadata)

    result = DebugAgent(requirement_analyzer=MutatingAnalyzer()).run(
        _task(nested=nested)
    )

    assert result.status is AgentStatus.SUCCESS
    assert nested == {"flag": True}


def test_debug_agent_isolates_mutation_between_pipeline_stages() -> None:
    class MutatingRetriever:
        def retrieve(self, request):
            request.metadata["nested"]["keep"] = False
            return []

    class InspectingAnalyzer:
        def analyze(self, request, evidence):
            assert request.metadata == {"nested": {"keep": True}}
            from embedded_copilot.debug.analyzer import DebugAnalyzer

            return DebugAnalyzer().analyze(request, evidence)

    result = DebugAgent(
        retriever=MutatingRetriever(),  # type: ignore[arg-type]
        debug_analyzer=InspectingAnalyzer(),  # type: ignore[arg-type]
    ).run(_task(nested={"keep": True}))

    assert result.status is AgentStatus.SUCCESS


def test_debug_agent_isolates_report_from_validator_mutation() -> None:
    class MutatingValidator:
        def validate(self, report):
            report.metadata["analysis_mode"] = "MUTATED"
            return {
                "success": True,
                "errors": [],
                "warnings": [],
                "metadata": {},
            }

    result = DebugAgent(validator=MutatingValidator()).run(_task())  # type: ignore[arg-type]

    report = DebugReport.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert report.metadata["analysis_mode"] == "unverified_rule_based"


@pytest.mark.parametrize(
    ("dependency", "stage", "output", "error_type"),
    [
        ("requirement_analyzer", "requirement_analysis", "debug requirement analysis failed", "DebugAnalysisError"),
        ("retriever", "knowledge_retrieval", "debug knowledge retrieval failed", "DebugKnowledgeError"),
        ("debug_analyzer", "finding_analysis", "debug finding analysis failed", "DebugAnalysisError"),
        ("planner", "planning", "debug planning failed", "DebugPlanningError"),
        ("validator", "validation", "debug report validation failed", "DebugValidationError"),
    ],
)
def test_debug_agent_safely_maps_stage_exceptions(
    dependency: str,
    stage: str,
    output: str,
    error_type: str,
) -> None:
    class Failing:
        def __getattr__(self, name: str):
            def fail(*args: object, **kwargs: object) -> object:
                raise RuntimeError(
                    "PRIVATE_FULL_LOG_SENTINEL C:/Users/private/source.c"
                )

            return fail

    result = DebugAgent(**{dependency: Failing()}).run(_task())

    assert result.status is AgentStatus.ERROR
    assert result.output == output
    assert result.metadata == {"stage": stage, "error_type": error_type}
    assert "PRIVATE_FULL_LOG_SENTINEL" not in str(result)
    assert "C:/Users" not in str(result)


def test_debug_agent_safely_rejects_malformed_stage_output() -> None:
    class MalformedRetriever:
        def retrieve(self, request):
            return [{"content": "PRIVATE_KNOWLEDGE_BODY"}]

    result = DebugAgent(retriever=MalformedRetriever()).run(_task())

    assert result.status is AgentStatus.ERROR
    assert result.metadata == {
        "stage": "knowledge_retrieval",
        "error_type": "DebugKnowledgeError",
    }
    assert "PRIVATE_KNOWLEDGE_BODY" not in str(result)


def test_debug_agent_rejects_path_like_custom_provenance_without_leak() -> None:
    class PathRetriever:
        def retrieve(self, request):
            from embedded_copilot.debug.models import DebugEvidence

            return [
                DebugEvidence(
                    source="LOCAL:doc",
                    content="advisory",
                    category="runtime",
                    metadata={
                        "id": "doc",
                        "title": "C:/Users/private/document",
                        "source": "LOCAL",
                        "score": None,
                    },
                )
            ]

    result = DebugAgent(retriever=PathRetriever()).run(_task())  # type: ignore[arg-type]

    assert result.status is AgentStatus.ERROR
    assert result.metadata["stage"] == "knowledge_retrieval"
    assert "C:/Users" not in str(result)


def test_debug_agent_rejects_unsuccessful_validation() -> None:
    class RejectingValidator:
        def validate(self, report):
            return {
                "success": False,
                "errors": ["PRIVATE_FULL_LOG_SENTINEL"],
                "warnings": [],
                "metadata": {},
            }

    result = DebugAgent(validator=RejectingValidator()).run(_task())

    assert result.status is AgentStatus.ERROR
    assert result.output == "debug report validation failed"
    assert "PRIVATE_FULL_LOG_SENTINEL" not in str(result)


def test_debug_agent_safely_maps_non_json_report_metadata() -> None:
    class NonSerializablePlanner:
        def plan(self, request, findings, documents):
            from embedded_copilot.debug.planner import DebugPlanner

            plan = DebugPlanner().plan(request, findings, documents)
            return plan.model_copy(update={"metadata": {"value": object()}})

    result = DebugAgent(planner=NonSerializablePlanner()).run(_task())  # type: ignore[arg-type]

    assert result.status is AgentStatus.ERROR
    assert result.output == "debug report assembly failed"
    assert result.metadata == {
        "stage": "report_assembly",
        "error_type": "DebugPlanningError",
    }
