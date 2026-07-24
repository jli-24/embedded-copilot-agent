from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.agents.types import AgentStatus
from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.input.models import UnifiedInputContext
from embedded_copilot.integration.context import (
    AgentExecutionResult,
    EngineeringContext,
    IntegrationKnowledgeContext,
    IntegrationTraceEvent,
)
from embedded_copilot.knowledge.models import (
    KnowledgeQuery,
    KnowledgeResult,
    KnowledgeSource,
)
from embedded_copilot.supervisor.context import KnowledgeContext


def _firmware_project() -> FirmwareProject:
    return FirmwareProject(
        name="camera",
        platform="ESP32",
        framework="ESP-IDF",
        files=[
            ProjectFile(
                path="main/main.c",
                content="sensitive generated source",
                language="C",
            )
        ],
        structure=["main"],
        metadata={"nested": {"values": ["original"]}},
    )


def test_engineering_context_is_frozen_and_deep_copies_nested_models() -> None:
    project = _firmware_project()
    result = AgentExecutionResult(
        agent_name="FirmwareAgent",
        status=AgentStatus.SUCCESS,
        result=project,
    )
    context = EngineeringContext(
        request="Build camera firmware",
        input_context=UnifiedInputContext(text="camera request"),
        agent_results=[result],
        trace=[
            IntegrationTraceEvent(
                sequence=1,
                stage="agent_executed",
                status="success",
                source_agent="FirmwareAgent",
                source_id="agent-result:FirmwareAgent",
            )
        ],
    )

    project.files.append(
        ProjectFile(path="main/late.c", content="late", language="C")
    )
    project.metadata["nested"]["values"].append("mutated")  # type: ignore[index,union-attr]

    assert isinstance(context.agent_results, tuple)
    assert isinstance(context.trace, tuple)
    stored = context.agent_results[0].result
    assert stored is not None
    assert stored.kind == "firmware"
    assert stored.file_paths == ("main/main.c",)
    assert "sensitive generated source" not in context.model_dump_json()
    assert "nested" not in context.model_dump_json()
    with pytest.raises(ValidationError):
        context.request = "mutated"  # type: ignore[misc]


def test_engineering_context_agent_evidence_has_no_mutable_nested_state() -> None:
    context = EngineeringContext(
        request="Build camera firmware",
        agent_results=(
            AgentExecutionResult(
                agent_name="FirmwareAgent",
                status=AgentStatus.SUCCESS,
                result=_firmware_project(),
            ),
        ),
    )
    stored = context.agent_results[0].result

    assert stored is not None
    assert isinstance(stored.file_paths, tuple)
    with pytest.raises((AttributeError, TypeError, ValidationError)):
        stored.file_paths += ("main/mutated.c",)  # type: ignore[attr-defined,misc]


def test_agent_execution_result_requires_matching_typed_result() -> None:
    with pytest.raises(ValidationError, match="does not match agent"):
        AgentExecutionResult(
            agent_name="HardwareAgent",
            status=AgentStatus.SUCCESS,
            result=_firmware_project(),
        )


def test_agent_execution_result_rejects_unsafe_direct_snapshot_payload() -> None:
    with pytest.raises(ValidationError, match="unsafe"):
        AgentExecutionResult.model_validate(
            {
                "agent_name": "DebugAgent",
                "status": "success",
                "result": {
                    "kind": "debug",
                    "project_name": "camera",
                    "error_type": "compile_error",
                    "summary": "ghp_private_token_value",
                },
            }
        )

    with pytest.raises(ValidationError, match="unsafe"):
        IntegrationTraceEvent(
            sequence=1,
            stage="agent_executed",
            status="success",
            source_agent="DebugAgent",
            source_id="mailto:private@example.com",
        )

    with pytest.raises(ValidationError, match="unsafe"):
        AgentExecutionResult.model_validate(
            {
                "agent_name": "DebugAgent",
                "source_id": "mailto:private@example.com",
                "status": "success",
                "result": {
                    "kind": "debug",
                    "project_name": "camera",
                    "error_type": "compile_error",
                    "summary": "Safe debug evidence.",
                },
            }
        )

    with pytest.raises(ValidationError, match="successful execution requires result"):
        AgentExecutionResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.SUCCESS,
            result=None,
        )

    with pytest.raises(ValidationError, match="failed execution must not contain result"):
        AgentExecutionResult(
            agent_name="FirmwareAgent",
            status=AgentStatus.ERROR,
            result=_firmware_project(),
        )


def test_integration_contracts_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EngineeringContext(request="firmware", unexpected=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        IntegrationTraceEvent(
            sequence=1,
            stage="agent_executed",
            status="success",
            source_agent="FirmwareAgent",
            source_id="agent-result:FirmwareAgent",
            path="C:\\private\\board.kicad_pcb",
        )


def test_engineering_context_projects_knowledge_provenance_without_content() -> None:
    knowledge = KnowledgeContext(
        query=KnowledgeQuery(query="camera", sources=[KnowledgeSource.LOCAL]),
        retrieved_documents=(
            KnowledgeResult(
                id="knowledge-1",
                title="Synthetic reference",
                content="PRIVATE_PDF_DOCUMENT_BODY",
                source=KnowledgeSource.LOCAL,
                metadata={"nested": {"values": ["private"]}},
            ),
        ),
        summary="Retrieved one result.",
    )

    context = EngineeringContext(
        request="camera",
        knowledge_context=knowledge,  # type: ignore[arg-type]
    )
    serialized = context.model_dump_json()

    assert context.knowledge_context is not None
    assert context.knowledge_context.source_ids == ("knowledge-1",)
    assert context.knowledge_context.sources == ("LOCAL",)
    assert "PRIVATE_PDF_DOCUMENT_BODY" not in serialized
    assert "private" not in serialized


def test_engineering_context_filters_unsafe_knowledge_provenance() -> None:
    knowledge = KnowledgeContext(
        query=KnowledgeQuery(query="camera", sources=[KnowledgeSource.LOCAL]),
        retrieved_documents=(
            KnowledgeResult(
                id="/Users/alice/private/file.pdf",
                title="Synthetic reference",
                content="PRIVATE_PDF_DOCUMENT_BODY",
                source=KnowledgeSource.LOCAL,
            ),
        ),
        summary="access_token=TOP_SECRET\nprivate document body",
    )

    context = EngineeringContext(request="camera", knowledge_context=knowledge)
    serialized = context.model_dump_json()

    assert context.knowledge_context is not None
    assert context.knowledge_context.source_ids == ()
    assert context.knowledge_context.result_count == 0
    assert context.knowledge_context.summary == "Retrieved 0 knowledge result(s)."
    assert "TOP_SECRET" not in serialized
    assert "/Users/" not in serialized

    with pytest.raises(ValidationError, match="unsafe"):
        IntegrationKnowledgeContext(
            source_ids=("mailto:private@example.com",),
            sources=("LOCAL",),
            result_count=1,
            summary="Retrieved one result.",
        )
