from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.models import ArtifactView
from embedded_copilot.copilot.session import project_artifact_view
from embedded_copilot.hardware_design.approval import DesignApproval
from embedded_copilot.hardware_design.artifact import HardwareDesignArtifact
from embedded_copilot.hardware_design.decision import DesignDecision
from embedded_copilot.hardware_design.evidence import DesignEvidence
from embedded_copilot.hardware_design.models import (
    DesignComponent,
    DesignModule,
    HardwareDesignBlueprint,
    PowerTree,
)


def artifact() -> HardwareDesignArtifact:
    evidence = DesignEvidence(
        evidence_id="evidence:1",
        source_id="datasheet:1",
        source_type="datasheet",
        location="structured:datasheet",
        content_summary="Structured Datasheet identifies ESP32-S3.",
        confidence=1.0,
    )
    decision = DesignDecision(
        decision_id="decision:1",
        decision_type="mcu_observation",
        decision="HardwarePlan identifies ESP32-S3.",
        reason="The observation is bound to structured Datasheet evidence.",
        evidence_ids=(evidence.evidence_id,),
        confidence=1.0,
    )
    blueprint = HardwareDesignBlueprint(
        project_name="Security Terminal",
        target_platform="ESP32",
        modules=(
            DesignModule(
                name="ESP32-S3",
                description="MCU observation copied from HardwarePlan.",
                source_ids=(evidence.source_id,),
            ),
            DesignModule(
                name="PIR",
                description="PIR observation copied from HardwarePlan.",
            ),
        ),
        components=(
            DesignComponent(
                name="PIR",
                category="sensor",
                purpose="PIR observation copied from HardwarePlan.",
            ),
        ),
        power_tree=PowerTree(
            input="unresolved",
            limitations=("Power topology is unresolved.",),
        ),
        limitations=("PIR connection endpoints are unresolved.",),
        source_ids=(evidence.source_id,),
    )
    return HardwareDesignArtifact(
        blueprint=blueprint,
        evidence=(evidence,),
        decisions=(decision,),
        approval=DesignApproval(),
    )


def test_artifact_view_is_narrow_read_only_projection() -> None:
    source = artifact()
    before = source.model_dump_json()

    view = project_artifact_view(artifact_id="artifact:1", artifact=source)

    assert isinstance(view, ArtifactView)
    assert view.artifact_id == "artifact:1"
    assert view.project_name == "Security Terminal"
    assert view.target_platform == "ESP32"
    assert view.components == ("ESP32-S3", "PIR")
    assert view.limitations == ("PIR connection endpoints are unresolved.",)
    assert view.evidence[0].model_dump(mode="json") == {
        "evidence_id": "evidence:1",
        "source_id": "datasheet:1",
        "summary": "Structured Datasheet identifies ESP32-S3.",
    }
    assert view.decisions[0].decision_id == "decision:1"
    assert view.decisions[0].evidence_ids == ("evidence:1",)
    assert source.model_dump_json() == before


def test_artifact_view_does_not_expose_or_invent_domain_fields() -> None:
    view = project_artifact_view(artifact_id="artifact:1", artifact=artifact())
    serialized = view.model_dump_json()

    assert set(ArtifactView.model_fields) == {
        "artifact_id",
        "project_name",
        "target_platform",
        "components",
        "limitations",
        "evidence",
        "decisions",
        "approval_status",
    }
    assert "artifact" not in ArtifactView.model_fields
    assert "connections" not in serialized
    assert "gpio_assignments" not in serialized
    assert "power_tree" not in serialized
    assert "MQ-2" not in serialized


def test_artifact_view_preserves_evidence_and_decision_order() -> None:
    source = artifact()
    second_evidence = source.evidence[0].model_copy(
        update={
            "evidence_id": "evidence:2",
            "content_summary": "Structured Datasheet identifies a second record.",
        }
    )
    second_decision = source.decisions[0].model_copy(
        update={
            "decision_id": "decision:2",
            "decision": "HardwarePlan contains a second observation.",
            "evidence_ids": (second_evidence.evidence_id,),
        }
    )
    expanded = source.model_copy(
        update={
            "evidence": (*source.evidence, second_evidence),
            "decisions": (*source.decisions, second_decision),
        }
    )

    view = project_artifact_view(artifact_id="artifact:1", artifact=expanded)

    assert [item.evidence_id for item in view.evidence] == ["evidence:1", "evidence:2"]
    assert [item.decision_id for item in view.decisions] == [
        "decision:1",
        "decision:2",
    ]


def test_artifact_view_rejects_unbound_or_ambiguous_evidence_links() -> None:
    projected = project_artifact_view(artifact_id="artifact:1", artifact=artifact())
    decision = projected.decisions[0]

    with pytest.raises(ValidationError):
        ArtifactView.model_validate(
            {
                **projected.model_dump(mode="python"),
                "evidence": (),
            }
        )
    with pytest.raises(ValidationError):
        ArtifactView.model_validate(
            {
                **projected.model_dump(mode="python"),
                "evidence": (*projected.evidence, projected.evidence[0]),
            }
        )
    with pytest.raises(ValidationError):
        ArtifactView.model_validate(
            {
                **projected.model_dump(mode="python"),
                "decisions": (decision, decision),
            }
        )
