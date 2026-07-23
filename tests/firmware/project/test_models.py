import pytest
from pydantic import ValidationError

from embedded_copilot.firmware.project.models import (
    FirmwareProject,
    ProjectFile,
    ProjectValidationResult,
)
from embedded_copilot.firmware import (
    FirmwareProject as PublicFirmwareProject,
    FirmwareProjectError,
    FirmwareProjectGenerator,
    FirmwareProjectValidator,
)
from embedded_copilot.firmware.exceptions import FirmwareIntelligenceError


def test_project_models_strip_contract_fields_but_preserve_content() -> None:
    project_file = ProjectFile(
        path=" main/main.c ",
        content="  mock/unverified content\n",
        language=" C ",
    )
    project = FirmwareProject(
        name=" demo ",
        platform=" ESP32 ",
        framework=" ESP-IDF ",
        files=[project_file],
        structure=[" main/ ", " main/main.c "],
    )

    assert project.name == "demo"
    assert project.platform == "ESP32"
    assert project.files[0].path == "main/main.c"
    assert project.files[0].content == "  mock/unverified content\n"
    assert project.structure == ["main/", "main/main.c"]


def test_project_models_are_frozen_and_forbid_extra_fields() -> None:
    project = FirmwareProject(name="demo", platform="ESP32")

    with pytest.raises(ValidationError):
        project.name = "changed"
    with pytest.raises(ValidationError):
        ProjectFile(path="main.c", content="mock", language="C", extra=True)


def test_project_validation_result_enforces_outcome_invariant() -> None:
    assert ProjectValidationResult(success=True).errors == []

    with pytest.raises(ValidationError):
        ProjectValidationResult(success=True, errors=["unexpected"])
    with pytest.raises(ValidationError):
        ProjectValidationResult(success=False)


def test_project_interfaces_are_public_and_errors_share_intelligence_base() -> None:
    assert PublicFirmwareProject is FirmwareProject
    assert FirmwareProjectGenerator is not None
    assert FirmwareProjectValidator is not None
    assert issubclass(FirmwareProjectError, FirmwareIntelligenceError)
