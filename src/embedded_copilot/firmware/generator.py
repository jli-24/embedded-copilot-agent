from __future__ import annotations

from collections.abc import Mapping, Sequence

from embedded_copilot.firmware.exceptions import FirmwareGenerationError
from embedded_copilot.firmware.models import FirmwareRequest, GeneratedCode, GeneratedFile
from embedded_copilot.firmware.platform import ESP32Platform, FirmwarePlatform, STM32Platform
from embedded_copilot.firmware.templates import TemplateManager, create_default_template_manager


TemplateBinding = tuple[str, str, str]
_DEFAULT_BINDINGS: dict[tuple[str, str], TemplateBinding] = {
    ("esp32", "gpio"): ("esp32_gpio", "main.c", "C"),
    ("esp32", "wifi"): ("esp32_wifi", "wifi.c", "C"),
    ("esp32", "camera"): ("esp32_camera", "camera.c", "C"),
    ("stm32", "uart"): ("stm32_uart", "main.c", "C"),
}


class FirmwareGenerator:
    """Deterministic mock generator with injectable platforms and templates."""

    def __init__(
        self,
        *,
        platforms: Sequence[FirmwarePlatform] | None = None,
        template_manager: TemplateManager | None = None,
        template_bindings: Mapping[tuple[str, str], TemplateBinding] | None = None,
    ) -> None:
        platform_items = (
            (ESP32Platform(), STM32Platform()) if platforms is None else platforms
        )
        self._platforms = {item.name.casefold(): item for item in platform_items}
        self._templates = template_manager or create_default_template_manager()
        self._bindings = dict(
            _DEFAULT_BINDINGS if template_bindings is None else template_bindings
        )

    def generate(self, request: FirmwareRequest) -> GeneratedCode:
        platform = self._platforms.get(request.platform.casefold())
        if platform is None:
            raise FirmwareGenerationError(f"unsupported platform: {request.platform}")

        validation = platform.validate_request(request)
        if not validation.success:
            raise FirmwareGenerationError("; ".join(validation.errors))

        files: list[GeneratedFile] = []
        filenames: set[str] = set()
        for peripheral in request.peripherals:
            binding = self._bindings.get((platform.name.casefold(), peripheral.casefold()))
            if binding is None:
                raise FirmwareGenerationError(
                    f"no mock template for {platform.name}/{peripheral}"
                )
            template_name, filename, language = binding
            try:
                content = self._templates.get_template(template_name)
            except KeyError as exc:
                raise FirmwareGenerationError(
                    f"missing mock template: {template_name}"
                ) from exc
            filename_key = filename.casefold()
            if filename_key in filenames:
                raise FirmwareGenerationError(f"duplicate output filename: {filename}")
            filenames.add(filename_key)
            files.append(
                GeneratedFile(filename=filename, content=content, language=language)
            )

        if not files:
            raise FirmwareGenerationError("request does not select a mock template")

        if platform.name == "ESP32" and "main.c" not in filenames:
            try:
                main_content = self._templates.get_template("esp32_main")
            except KeyError as exc:
                raise FirmwareGenerationError(
                    "missing mock template: esp32_main"
                ) from exc
            files.insert(
                0,
                GeneratedFile(filename="main.c", content=main_content, language="C"),
            )

        project_name_value = request.metadata.get("project_name")
        project_name = (
            project_name_value.strip()
            if isinstance(project_name_value, str) and project_name_value.strip()
            else f"{platform.name.casefold()}_firmware"
        )
        return GeneratedCode(
            project_name=project_name,
            platform=platform.name,
            files=files,
        )
