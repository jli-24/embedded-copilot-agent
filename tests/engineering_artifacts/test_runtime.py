from __future__ import annotations

from embedded_copilot.engineering_artifacts import (
    ArtifactFindingCode,
    ArtifactStatus,
    ArtifactType,
    ConstraintCategory,
    FirmwareModuleGroup,
    create_engineering_artifact_runtime,
)


def _report(request):
    return (
        create_engineering_artifact_runtime()
        .engineering_artifact_port()
        .generate(request)
    )


def test_firmware_proposal_maps_to_safe_structure(generation_request) -> None:
    report = _report(generation_request)
    assert tuple(
        item.module_group for item in report.firmware_artifact.modules
    ) == tuple(FirmwareModuleGroup)
    assert report.firmware_artifact.code_skeletons
    serialized = report.firmware_artifact.model_dump_json().casefold()
    forbidden = (
        "esp_camera_init",
        "hal_gpio_init",
        "idf.py",
        "cmakelists",
        '.c"',
        '.cpp"',
        '.h"',
        "source_code",
        "file_content",
        "filesystem_path",
    )
    assert not any(value in serialized for value in forbidden)


def test_hardware_proposal_maps_to_unified_model_without_inference(
    generation_request,
) -> None:
    report = _report(generation_request)
    model = report.unified_hardware_model
    assert model == report.hardware_artifact.unified_model
    assert model.components
    assert tuple(item.component_id for item in model.components) == tuple(
        sorted(item.component_id for item in model.components)
    )
    assert model.interfaces
    assert all(item.target_component is None for item in model.interfaces)
    assert {item.category for item in model.constraints}.issuperset(
        {
            ConstraintCategory.FUNCTIONAL,
            ConstraintCategory.COMMUNICATION,
            ConstraintCategory.POWER,
            ConstraintCategory.HARDWARE,
        }
    )
    serialized = model.model_dump_json().casefold()
    forbidden = (
        "pin",
        "gpio",
        "footprint",
        "package",
        "voltage",
        "register",
        "impedance",
        "line_width",
        "placement",
    )
    assert not any(value in serialized for value in forbidden)


def test_artifact_status_and_review_findings_are_projection_only(
    generation_request,
) -> None:
    report = _report(generation_request)
    status = {
        item.artifact_type: item.status for item in report.artifact_contract.artifacts
    }
    assert status[ArtifactType.FIRMWARE_STRUCTURE] is ArtifactStatus.REVIEW_REQUIRED
    assert status[ArtifactType.HARDWARE_MODEL] is ArtifactStatus.REVIEW_REQUIRED
    assert status[ArtifactType.SCHEMATIC_INTENT] is ArtifactStatus.REVIEW_REQUIRED
    assert status[ArtifactType.PCB_CONSTRAINT] is ArtifactStatus.GENERATED
    assert report.candidate_semantics == "unverified"
    assert report.review_required is True
    assert report.review.finding_codes == tuple(ArtifactFindingCode)
    contract_json = report.artifact_contract.model_dump_json().casefold()
    assert "completed" not in contract_json
    assert "verified_artifact" not in contract_json


def test_validation_is_review_only_and_does_not_enter_artifact_sources(
    generation_request,
) -> None:
    with_validation = _report(generation_request)
    without_validation = _report(
        generation_request.model_copy(update={"validation_report": None}, deep=True)
    )
    assert with_validation.firmware_artifact == without_validation.firmware_artifact
    assert with_validation.hardware_artifact == without_validation.hardware_artifact
    assert (
        with_validation.artifact_contract.artifact_source_fingerprint
        == without_validation.artifact_contract.artifact_source_fingerprint
    )
    assert with_validation.review.validation_report_fingerprint is not None
    assert with_validation.review.validation_coverage_count > 0
    assert without_validation.review.validation_report_fingerprint is None
    assert without_validation.review.validation_coverage_count == 0


def test_generation_does_not_modify_caller_owned_input(generation_request) -> None:
    before = generation_request.model_dump(mode="python")
    _report(generation_request)
    assert generation_request.model_dump(mode="python") == before
