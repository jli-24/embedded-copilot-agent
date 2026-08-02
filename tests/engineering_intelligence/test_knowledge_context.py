from __future__ import annotations

from embedded_copilot.datasheet_runtime import (
    DatasheetResponse,
    DatasheetSummary,
)
from embedded_copilot.engineering_intelligence import (
    DatasheetKnowledgeCategory,
    EngineeringContextRequest,
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EvidenceStatus,
    WebResearchPort,
    create_engineering_intelligence_runtime,
    engineering_evidence_fingerprint,
    project_datasheet_knowledge,
    project_engineering_project,
)

from .conftest import NOW


def _evidence(
    *,
    evidence_id: str,
    value: str,
    status: EvidenceStatus = EvidenceStatus.VERIFIED,
) -> EngineeringKnowledgeEvidence:
    values = dict(
        evidence_id=evidence_id,
        source_type=EngineeringKnowledgeSourceType.RAG,
        fact_type="MCU_CAPABILITY",
        key="wifi_support",
        value=value,
        summary="Engineering capability reference.",
        status=status,
        confidence=1.0 if status is EvidenceStatus.VERIFIED else 0.0,
        reference_ids=(f"reference-{evidence_id}",),
        observed_at=NOW,
    )
    return EngineeringKnowledgeEvidence(
        **values,
        fingerprint=engineering_evidence_fingerprint(**values),
    )


def test_datasheet_integration_projects_metadata_without_parsing() -> None:
    response = DatasheetResponse(
        summary=DatasheetSummary(file_id="datasheet-1"),
        review_required=True,
    )
    projection = project_datasheet_knowledge(response, observed_at=NOW)

    assert projection.source_id == "datasheet-1"
    assert projection.facts == ()
    assert projection.review_required is True
    assert projection.categories == tuple(DatasheetKnowledgeCategory)
    serialized = projection.model_dump_json().casefold()
    for forbidden in ("path", "content", "bytes", "base64", "pdf"):
        assert forbidden not in serialized


def test_context_fusion_is_sorted_deterministic_and_conflict_safe(
    interface_project,
) -> None:
    port = create_engineering_intelligence_runtime().engineering_intelligence_port()
    project = project_engineering_project(interface_project)
    requirement = port.analyze_requirement(public_requirement(project))
    plan = port.create_plan(requirement)
    conflicting = (
        _evidence(evidence_id="evidence-b", value="UNSUPPORTED"),
        _evidence(evidence_id="evidence-a", value="SUPPORTED"),
    )

    first = port.build_context(
        EngineeringContextRequest(
            project=project,
            requirement=requirement,
            plan=plan,
            evidence=conflicting,
            requested_at=NOW,
        )
    )
    second = port.build_context(
        EngineeringContextRequest(
            project=project,
            requirement=requirement,
            plan=plan,
            evidence=tuple(reversed(conflicting)),
            requested_at=NOW,
        )
    )

    assert first == second
    assert tuple(item.evidence_id for item in first.evidence) == (
        "evidence-a",
        "evidence-b",
    )
    assert first.conflict_count == 1
    assert first.review_required is True
    assert all(
        decision.candidate_semantics == "unverified" for decision in first.decisions
    )


def test_web_research_is_protocol_only() -> None:
    assert set(WebResearchPort.__dict__) >= {"research"}


def public_requirement(project):
    from embedded_copilot.engineering_intelligence import EngineeringRequirementRequest

    return EngineeringRequirementRequest(
        project=project,
        session_id="session-1",
        message_id="message-1",
        requirement_summary="Design an ESP32-S3 camera with Wi-Fi.",
        requested_at=NOW,
    )
