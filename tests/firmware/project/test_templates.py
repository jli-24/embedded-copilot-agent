import pytest

from embedded_copilot.firmware.project.templates import (
    ProjectTemplateManager,
    create_default_project_template_manager,
)
from embedded_copilot.firmware.templates import create_default_template_manager


def test_project_template_manager_registers_gets_and_lists_in_order() -> None:
    manager = ProjectTemplateManager()
    manager.register_template(" first ", "mock/unverified first")
    manager.register_template("second", "mock/unverified second")

    assert manager.get_template(" first ") == "mock/unverified first"
    assert manager.list_templates() == ["first", "second"]


def test_project_template_manager_rejects_duplicate_and_missing_names() -> None:
    manager = ProjectTemplateManager()
    manager.register_template("readme", "mock/unverified")

    with pytest.raises(ValueError, match="already registered"):
        manager.register_template(" readme ", "different")
    with pytest.raises(KeyError):
        manager.get_template("missing")


def test_default_project_templates_are_mock_only_and_isolated() -> None:
    project_manager = create_default_project_template_manager()
    legacy_manager = create_default_template_manager()

    assert project_manager.list_templates() == [
        "esp32_wifi_header",
        "esp32_readme",
        "esp32_cmake",
        "stm32_uart_source",
        "stm32_uart_header",
        "stm32_readme",
    ]
    for name in project_manager.list_templates():
        content = project_manager.get_template(name).lower()
        assert "mock" in content
        assert "unverified" in content
    assert set(project_manager.list_templates()).isdisjoint(
        legacy_manager.list_templates()
    )
