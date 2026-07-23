from __future__ import annotations


ESP32_WIFI_HEADER = """/* Mock/unverified ESP32 WiFi project header. */\n"""
ESP32_README = """# Mock/unverified ESP32 firmware project\n"""
ESP32_CMAKE = """# Mock/unverified ESP32 build structure; not a real build file.\n"""
STM32_UART_SOURCE = """/* Mock/unverified STM32 UART project source. */\n"""
STM32_UART_HEADER = """/* Mock/unverified STM32 UART project header. */\n"""
STM32_README = """# Mock/unverified STM32 firmware project\n"""


class ProjectTemplateManager:
    def __init__(self) -> None:
        self._templates: dict[str, str] = {}

    def register_template(self, name: str, content: str) -> None:
        key = name.strip()
        if not key:
            raise ValueError("project template name must not be empty")
        if not content:
            raise ValueError("project template content must not be empty")
        if key in self._templates:
            raise ValueError(f"project template already registered: {key}")
        self._templates[key] = content

    def get_template(self, name: str) -> str:
        return self._templates[name.strip()]

    def list_templates(self) -> list[str]:
        return list(self._templates)


def create_default_project_template_manager() -> ProjectTemplateManager:
    manager = ProjectTemplateManager()
    manager.register_template("esp32_wifi_header", ESP32_WIFI_HEADER)
    manager.register_template("esp32_readme", ESP32_README)
    manager.register_template("esp32_cmake", ESP32_CMAKE)
    manager.register_template("stm32_uart_source", STM32_UART_SOURCE)
    manager.register_template("stm32_uart_header", STM32_UART_HEADER)
    manager.register_template("stm32_readme", STM32_README)
    return manager
