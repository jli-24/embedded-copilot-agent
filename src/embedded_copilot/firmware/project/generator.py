from __future__ import annotations

from collections.abc import Mapping

from embedded_copilot.firmware.exceptions import (
    FirmwareGenerationError,
    FirmwareProjectError,
)
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.models import GeneratedCode
from embedded_copilot.firmware.planner.models import FirmwarePlan
from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.firmware.project.templates import (
    ProjectTemplateManager,
    create_default_project_template_manager,
)
from embedded_copilot.firmware.validator import FirmwareValidator


_SUPPORTED_PERIPHERALS: Mapping[str, frozenset[str]] = {
    "esp32": frozenset({"gpio", "wifi", "camera"}),
    "stm32": frozenset({"uart"}),
}

_PATH_BINDINGS: Mapping[str, Mapping[str, str]] = {
    "esp32": {
        "main.c": "main/main.c",
        "wifi.c": "main/wifi.c",
        "camera.c": "main/camera.c",
    },
    "stm32": {"main.c": "Core/Src/main.c"},
}


class FirmwareProjectGenerator:
    """Organize legacy mock code into an in-memory firmware project."""

    def __init__(
        self,
        *,
        code_generator: FirmwareGenerator | None = None,
        code_validator: FirmwareValidator | None = None,
        template_manager: ProjectTemplateManager | None = None,
    ) -> None:
        self._code_generator = (
            code_generator if code_generator is not None else FirmwareGenerator()
        )
        self._code_validator = (
            code_validator if code_validator is not None else FirmwareValidator()
        )
        self._templates = (
            template_manager
            if template_manager is not None
            else create_default_project_template_manager()
        )

    def generate(self, plan: FirmwarePlan) -> FirmwareProject:
        platform_key = plan.platform.casefold()
        supported = _SUPPORTED_PERIPHERALS.get(platform_key)
        if supported is None:
            raise FirmwareProjectError("unsupported firmware project platform")

        peripheral_keys = [peripheral.casefold() for peripheral in plan.peripherals]
        unsupported = [key for key in peripheral_keys if key not in supported]
        if unsupported:
            raise FirmwareProjectError("firmware project contains unsupported peripherals")

        try:
            generated = self._code_generator.generate(
                plan.to_firmware_request(
                    requirement="Generate a mock/unverified project from FirmwarePlan."
                )
            )
        except FirmwareGenerationError as exc:
            raise FirmwareProjectError("legacy mock code generation failed") from exc

        validation = self._code_validator.validate(generated)
        if not validation.success:
            raise FirmwareProjectError("legacy mock code validation failed")
        if generated.platform.casefold() != platform_key:
            raise FirmwareProjectError("legacy generated platform does not match plan")

        try:
            files = self._organize_files(generated, platform_key, peripheral_keys)
        except KeyError as exc:
            raise FirmwareProjectError("required project template is missing") from exc

        if any(
            "mock" not in project_file.content.casefold()
            or "unverified" not in project_file.content.casefold()
            for project_file in files
        ):
            raise FirmwareProjectError("project files must be marked mock/unverified")

        project_name = plan.project_name or f"{platform_key}_project"
        return FirmwareProject(
            name=project_name,
            platform=plan.platform,
            framework=plan.framework,
            files=files,
            structure=_build_structure(platform_key, files),
            metadata={
                "generation_mode": "mock_unverified",
                "components": list(plan.components),
                "peripherals": list(plan.peripherals),
                "dependencies": list(plan.dependencies),
            },
        )

    def _organize_files(
        self,
        generated: GeneratedCode,
        platform_key: str,
        peripheral_keys: list[str],
    ) -> list[ProjectFile]:
        bindings = _PATH_BINDINGS[platform_key]
        files: list[ProjectFile] = []
        for generated_file in generated.files:
            path = bindings.get(generated_file.filename.casefold())
            if path is None:
                raise FirmwareProjectError("legacy generator returned an unknown file")
            files.append(
                ProjectFile(
                    path=path,
                    content=generated_file.content,
                    language=generated_file.language,
                )
            )
            if platform_key == "esp32" and path == "main/wifi.c":
                files.append(
                    _template_file(
                        self._templates,
                        "esp32_wifi_header",
                        "main/wifi.h",
                        "C Header",
                    )
                )

        if platform_key == "esp32":
            files.extend(
                [
                    _template_file(
                        self._templates, "esp32_readme", "README.md", "Markdown"
                    ),
                    _template_file(
                        self._templates,
                        "esp32_cmake",
                        "CMakeLists.txt",
                        "CMake",
                    ),
                ]
            )
        else:
            if "uart" in peripheral_keys:
                files.extend(
                    [
                        _template_file(
                            self._templates,
                            "stm32_uart_source",
                            "Core/Src/uart.c",
                            "C",
                        ),
                        _template_file(
                            self._templates,
                            "stm32_uart_header",
                            "Core/Inc/uart.h",
                            "C Header",
                        ),
                    ]
                )
            files.append(
                _template_file(
                    self._templates, "stm32_readme", "README.md", "Markdown"
                )
            )
        return files


def _template_file(
    manager: ProjectTemplateManager,
    template_name: str,
    path: str,
    language: str,
) -> ProjectFile:
    return ProjectFile(
        path=path,
        content=manager.get_template(template_name),
        language=language,
    )


def _build_structure(platform_key: str, files: list[ProjectFile]) -> list[str]:
    paths = [project_file.path for project_file in files]
    if platform_key == "esp32":
        return ["main/", *[path for path in paths if path.startswith("main/")],
                *[path for path in paths if "/" not in path]]
    return [
        "Core/",
        "Core/Src/",
        *[path for path in paths if path.startswith("Core/Src/")],
        "Core/Inc/",
        *[path for path in paths if path.startswith("Core/Inc/")],
        *[path for path in paths if "/" not in path],
    ]
