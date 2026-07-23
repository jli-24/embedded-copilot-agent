import pytest

from embedded_copilot.agents.types import AgentStatus, AgentTask
from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.exceptions import FirmwareProjectError
from embedded_copilot.firmware.models import (
    GeneratedCode,
    GeneratedFile,
    ValidationResult,
)
from embedded_copilot.firmware.project.models import (
    FirmwareProject,
    ProjectFile,
    ProjectValidationResult,
)


def _project() -> FirmwareProject:
    return FirmwareProject(
        name="demo",
        platform="ESP32",
        framework="ESP-IDF",
        files=[
            ProjectFile(
                path="main/main.c",
                content="/* mock/unverified */",
                language="C",
            )
        ],
        structure=["main/", "main/main.c"],
        metadata={"peripherals": ["GPIO"]},
    )


def test_agent_returns_structured_project_and_metadata() -> None:
    result = FirmwareAgent().run(
        AgentTask(
            task_id="project-1",
            task_type="firmware",
            requirement="ESP32 ESP-IDF GPIO WiFi",
            metadata={"project_name": "sensor_node"},
        )
    )

    project = FirmwareProject.model_validate_json(result.output)
    assert result.status is AgentStatus.SUCCESS
    assert project.name == "sensor_node"
    assert [item.path for item in project.files] == [
        "main/main.c",
        "main/wifi.c",
        "main/wifi.h",
        "README.md",
        "CMakeLists.txt",
    ]
    assert result.metadata["firmware_project"] == project.model_dump(mode="json")
    assert result.metadata["firmware_plan"]["project_name"] == "sensor_node"
    assert result.metadata["retrieved_documents"] == []
    assert result.metadata["validation"]["success"] is True


class _LegacyGenerator:
    def __init__(self) -> None:
        self.called = False

    def generate(self, request):
        self.called = True
        return GeneratedCode(
            project_name="legacy",
            platform="ESP32",
            files=[
                GeneratedFile(
                    filename="main.c",
                    content="/* mock/unverified legacy */",
                    language="C",
                )
            ],
        )


class _LegacyValidator:
    def __init__(self) -> None:
        self.called = False

    def validate(self, generated):
        self.called = True
        return ValidationResult(success=True)


def test_agent_preserves_legacy_generator_and_validator_injection() -> None:
    generator = _LegacyGenerator()
    validator = _LegacyValidator()
    result = FirmwareAgent(generator=generator, validator=validator).run(
        AgentTask(
            task_id="project-2",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert generator.called is True
    assert validator.called is True


class _ProjectGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self.called = False
        self.fail = fail

    def generate(self, plan):
        self.called = True
        if self.fail:
            raise FirmwareProjectError("private C:\\Users\\secret\\project")
        return _project()


class _ProjectValidator:
    def __init__(self, *, success: bool = True) -> None:
        self.called = False
        self.success = success

    def validate(self, project):
        self.called = True
        return (
            ProjectValidationResult(success=True)
            if self.success
            else ProjectValidationResult(
                success=False,
                errors=["missing required project file: README.md"],
            )
        )


def test_agent_uses_injected_project_pipeline() -> None:
    generator = _ProjectGenerator()
    validator = _ProjectValidator()
    result = FirmwareAgent(
        project_generator=generator,
        project_validator=validator,
    ).run(
        AgentTask(
            task_id="project-3",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.SUCCESS
    assert generator.called is True
    assert validator.called is True


def test_agent_rejects_ambiguous_generator_injection() -> None:
    with pytest.raises(ValueError, match="project_generator"):
        FirmwareAgent(
            generator=_LegacyGenerator(),
            project_generator=_ProjectGenerator(),
        )


def test_agent_maps_project_errors_without_private_details() -> None:
    result = FirmwareAgent(project_generator=_ProjectGenerator(fail=True)).run(
        AgentTask(
            task_id="project-4",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.metadata["error_type"] == "FirmwareProjectError"
    assert result.output == "firmware project generation failed"
    assert "Users" not in result.output


def test_agent_returns_structured_project_validation_failure() -> None:
    result = FirmwareAgent(
        project_generator=_ProjectGenerator(),
        project_validator=_ProjectValidator(success=False),
    ).run(
        AgentTask(
            task_id="project-5",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    assert result.status is AgentStatus.ERROR
    assert result.output == "firmware project validation failed"
    assert result.metadata["firmware_project"] == {
        "status": "rejected",
        "platform": "ESP32",
        "file_count": 1,
    }
    assert result.metadata["validation"]["success"] is False


class _UnsafeProjectGenerator:
    def generate(self, plan):
        return FirmwareProject(
            name="C:/Users/private/project",
            platform="ESP32",
            files=[
                ProjectFile(
                    path="C:/Users/private/main.c",
                    content="private-source-content",
                    language="C",
                )
            ],
            structure=["C:/Users/private/main.c"],
        )


def test_agent_redacts_invalid_project_paths_and_content() -> None:
    result = FirmwareAgent(project_generator=_UnsafeProjectGenerator()).run(
        AgentTask(
            task_id="project-6",
            task_type="firmware",
            requirement="ESP32 GPIO",
        )
    )

    serialized_result = f"{result.output} {result.metadata}"
    assert result.status is AgentStatus.ERROR
    assert "C:/Users" not in serialized_result
    assert "private-source-content" not in serialized_result
