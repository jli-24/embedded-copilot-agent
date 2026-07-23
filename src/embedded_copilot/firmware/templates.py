from __future__ import annotations


GPIO_TEMPLATE = """/* Mock unverified ESP32 GPIO firmware. */\nint main(void) { return 0; }\n"""
ESP32_MAIN_TEMPLATE = """/* Mock unverified ESP32 project entry. */\nint main(void) { return 0; }\n"""
WIFI_TEMPLATE = """/* Mock unverified ESP32 WiFi component. */\nvoid wifi_mock_init(void) {}\n"""
CAMERA_TEMPLATE = """/* Mock unverified ESP32 Camera component. */\nvoid camera_mock_init(void) {}\n"""
UART_TEMPLATE = """/* Mock unverified STM32 UART firmware. */\nint main(void) { return 0; }\n"""


class TemplateManager:
    def __init__(self) -> None:
        self._templates: dict[str, str] = {}

    def register_template(self, name: str, content: str) -> None:
        key = name.strip()
        if not key:
            raise ValueError("template name must not be empty")
        if not content:
            raise ValueError("template content must not be empty")
        if key in self._templates:
            raise ValueError(f"template already registered: {key}")
        self._templates[key] = content

    def get_template(self, name: str) -> str:
        return self._templates[name.strip()]

    def list_templates(self) -> list[str]:
        return list(self._templates)


def create_default_template_manager() -> TemplateManager:
    manager = TemplateManager()
    manager.register_template("esp32_main", ESP32_MAIN_TEMPLATE)
    manager.register_template("esp32_gpio", GPIO_TEMPLATE)
    manager.register_template("esp32_wifi", WIFI_TEMPLATE)
    manager.register_template("esp32_camera", CAMERA_TEMPLATE)
    manager.register_template("stm32_uart", UART_TEMPLATE)
    return manager
