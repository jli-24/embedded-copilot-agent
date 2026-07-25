from __future__ import annotations

from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.datasheet.models import DatasheetElectricalSpec
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.hardware_design.models import GPIOAssignmentStatus
from embedded_copilot.hardware_design.projector import project, project_artifact

from tests.engineering.fixtures import datasheet_model, firmware_review


def _plan(*, with_rag_evidence: bool = False) -> HardwarePlan:
    return HardwarePlan(
        project_name="ESP32-S3 Smart Security Terminal",
        platform="ESP32",
        mcu="ESP32-S3",
        components=[
            HardwareComponent(
                name="Camera",
                category="sensor",
                interface=["SPI"],
                description="Camera copied from the explicit HardwarePlan.",
                metadata=(
                    {"evidence_document_id": "rag:camera-1"}
                    if with_rag_evidence
                    else {}
                ),
            ),
            HardwareComponent(
                name="Power stage candidate",
                category="power",
                interface=[],
                description="Unverified power component copied from HardwarePlan.",
            ),
        ],
        interfaces=["SPI", "GPIO"],
        power_requirements=["Determine the input rail from authorized evidence."],
        constraints=["Confirm all electrical limits."],
        rationale="Existing unverified plan.",
        metadata=(
            {"evidence_document_ids": ["rag:camera-1"]} if with_rag_evidence else {}
        ),
    )


def test_plan_only_projection_preserves_order_without_inventing_design() -> None:
    plan = _plan()
    before = plan.model_dump(mode="json")

    blueprint = project(plan)

    assert [item.name for item in blueprint.modules] == [
        "ESP32-S3",
        "Camera",
        "Power stage candidate",
    ]
    assert [item.name for item in blueprint.components] == [
        "Camera",
        "Power stage candidate",
    ]
    assert blueprint.connections == ()
    assert blueprint.gpio_assignments == ()
    assert blueprint.power_tree.input == "unresolved"
    assert blueprint.power_tree.stages == ("Power stage candidate",)
    assert blueprint.power_tree.consumers == ()
    assert not hasattr(blueprint.power_tree, "voltage")
    assert not hasattr(blueprint.power_tree, "current")
    assert any(
        item == "Unresolved connection endpoints for interface SPI."
        for item in blueprint.limitations
    )
    assert any(
        "ESP32-S3" in item and "evidence" in item for item in blueprint.limitations
    )
    assert plan.model_dump(mode="json") == before


def test_projector_uses_only_explicit_rag_ids_for_component_evidence() -> None:
    artifact = project_artifact(_plan(with_rag_evidence=True))

    assert [item.source_type.value for item in artifact.evidence] == ["rag"]
    assert artifact.evidence[0].source_id == "rag:camera-1"
    assert "references" in artifact.evidence[0].content_summary
    camera = next(
        item for item in artifact.blueprint.components if item.name == "Camera"
    )
    assert camera.source_ids == ("rag:camera-1",)
    assert len(artifact.decisions) == 1
    assert artifact.decisions[0].status.value == "PROPOSED"
    assert artifact.approval.status.value == "PROPOSED"
    assert artifact.approval.revision == 1


def test_envelope_projection_summarizes_records_without_copying_body_text() -> None:
    envelope = RealEngineeringEnvelope(
        datasheet=datasheet_model(),
        firmware_review=firmware_review(),
    )

    artifact = project_artifact(_plan(), envelope)
    serialized = artifact.model_dump_json()

    assert {item.source_type.value for item in artifact.evidence} == {
        "datasheet",
        "firmware",
    }
    assert "Embedded Flash function" not in serialized
    assert "camera_config_t" not in serialized
    assert "camera.c" not in serialized
    assert artifact.blueprint.connections == ()
    assert len(artifact.blueprint.gpio_assignments) == 1
    assignment = artifact.blueprint.gpio_assignments[0]
    assert assignment.gpio == "GPIO8"
    assert assignment.function == "Camera"
    assert assignment.interface == "unresolved"
    assert assignment.status is GPIOAssignmentStatus.CONFLICT
    assert set(assignment.source_ids) == {
        "attachment:datasheet-1",
        "attachment:source-1",
    }


def test_firmware_gpio_is_unresolved_without_existing_crosscheck_evidence() -> None:
    review = firmware_review().model_copy(
        update={
            "gpio_assignments": (
                firmware_review()
                .gpio_assignments[0]
                .model_copy(update={"pin": "GPIO4", "line": 9}),
            )
        }
    )
    envelope = RealEngineeringEnvelope(
        datasheet=datasheet_model(),
        firmware_review=review,
    )

    blueprint = project(_plan(), envelope)

    assert len(blueprint.gpio_assignments) == 1
    assignment = blueprint.gpio_assignments[0]
    assert assignment.gpio == "GPIO4"
    assert assignment.status is GPIOAssignmentStatus.UNRESOLVED
    assert "hardware correctness is unresolved" in assignment.reason


def test_projection_json_is_deterministic_and_sources_are_sorted() -> None:
    plan = _plan(with_rag_evidence=True)
    envelope = RealEngineeringEnvelope(
        datasheet=datasheet_model(),
        firmware_review=firmware_review(),
    )

    first = project_artifact(plan, envelope).model_dump_json()
    second = project_artifact(
        plan.model_copy(deep=True), envelope.model_copy(deep=True)
    )

    assert second.model_dump_json() == first
    assert second.blueprint.source_ids == tuple(sorted(second.blueprint.source_ids))


def test_esp32_name_does_not_trigger_common_knowledge_inference() -> None:
    blueprint = project(_plan())
    serialized = blueprint.model_dump_json()

    assert "3.3" not in serialized
    assert "GPIO4" not in serialized
    assert "pull-up" not in serialized
    assert blueprint.connections == ()


def test_projection_deduplicates_datasheet_power_evidence() -> None:
    specification = DatasheetElectricalSpec(
        parameter="Operating voltage",
        min_value=3.0,
        max_value=3.6,
        unit="V",
    )
    datasheet = datasheet_model().model_copy(
        update={
            "electrical_specs": (specification,),
            "power_requirements": (specification,),
        }
    )

    artifact = project_artifact(
        _plan(),
        RealEngineeringEnvelope(datasheet=datasheet),
    )

    evidence_ids = [item.evidence_id for item in artifact.evidence]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert (
        sum("Operating voltage" in item.content_summary for item in artifact.evidence)
        == 1
    )


def test_projection_omits_absolute_paths_from_legacy_plan_fields() -> None:
    unsafe = _plan().model_copy(
        update={
            "project_name": r"C:\Users\private\project",
            "mcu": r"C:\Users\private\mcu",
            "components": [
                _plan()
                .components[0]
                .model_copy(
                    update={
                        "name": r"C:\Users\private\camera",
                        "metadata": {
                            "evidence_document_id": r"C:\Users\private\source.pdf"
                        },
                    }
                )
            ],
        }
    )

    serialized = project_artifact(unsafe).model_dump_json()

    assert "C:" not in serialized
    assert "Users" not in serialized
    assert "private" not in serialized
