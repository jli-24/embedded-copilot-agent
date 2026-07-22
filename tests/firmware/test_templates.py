import pytest

from embedded_copilot.firmware.templates import (
    GPIO_TEMPLATE,
    TemplateManager,
    create_default_template_manager,
)


def test_template_manager_registers_gets_and_lists_in_order() -> None:
    manager = TemplateManager()
    manager.register_template("first", "one")
    manager.register_template("second", "two")

    assert manager.get_template("first") == "one"
    assert manager.list_templates() == ["first", "second"]


def test_template_manager_rejects_duplicates_and_missing_templates() -> None:
    manager = TemplateManager()
    manager.register_template("gpio", "content")

    with pytest.raises(ValueError, match="already registered"):
        manager.register_template("gpio", "other")
    with pytest.raises(KeyError):
        manager.get_template("missing")


def test_default_templates_are_mock_only() -> None:
    manager = create_default_template_manager()

    assert manager.get_template("esp32_gpio") == GPIO_TEMPLATE
    assert "mock" in GPIO_TEMPLATE.lower()
    assert "unverified" in GPIO_TEMPLATE.lower()
