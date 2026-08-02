from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import embedded_copilot.engineering_intelligence as public
from embedded_copilot.engineering_intelligence import (
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EngineeringProjectContextProjection,
    EvidenceStatus,
    project_engineering_project,
)

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)


def test_public_contracts_are_frozen_strict_and_tuple_only(interface_project) -> None:
    project = project_engineering_project(interface_project)
    evidence = EngineeringKnowledgeEvidence(
        evidence_id="evidence-1",
        source_type=EngineeringKnowledgeSourceType.RAG,
        fact_type="MCU_CAPABILITY",
        key="wifi_support",
        value="SUPPORTED",
        summary="Verified Wi-Fi capability reference.",
        status=EvidenceStatus.VERIFIED,
        confidence=1.0,
        reference_ids=("reference-1",),
        observed_at=NOW,
        fingerprint=public.engineering_evidence_fingerprint(
            evidence_id="evidence-1",
            source_type=EngineeringKnowledgeSourceType.RAG,
            fact_type="MCU_CAPABILITY",
            key="wifi_support",
            value="SUPPORTED",
            summary="Verified Wi-Fi capability reference.",
            status=EvidenceStatus.VERIFIED,
            confidence=1.0,
            reference_ids=("reference-1",),
            observed_at=NOW,
        ),
    )

    assert project.project_id == interface_project.project_id
    assert project.source_fingerprint == interface_project.fingerprint
    assert project is not interface_project
    with pytest.raises(ValidationError):
        project.name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringKnowledgeEvidence.model_validate(
            {**evidence.model_dump(), "unexpected": "value"}
        )
    with pytest.raises(ValidationError):
        EngineeringProjectContextProjection(
            **{
                **project.model_dump(),
                "reference_ids": ["board-esp32-s3"],
            }
        )


def test_project_adapter_deep_copies_and_revalidates(interface_project) -> None:
    before = interface_project.model_dump(mode="json")
    first = project_engineering_project(interface_project)
    second = project_engineering_project(interface_project)

    assert first == second
    assert first is not second
    assert interface_project.model_dump(mode="json") == before


def test_root_exports_do_not_expose_internal_agents() -> None:
    for forbidden in (
        "_RequirementAgent",
        "_PlanningAgent",
        "_EngineeringIntelligenceService",
        "RequirementExtractor",
    ):
        assert not hasattr(public, forbidden)
    assert set(public.EngineeringIntelligenceRuntime.__dict__) & {
        "engineering_intelligence_port"
    } == {"engineering_intelligence_port"}
