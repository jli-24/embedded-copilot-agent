import pytest

from embedded_copilot.core.capability import CapabilityRegistry


def test_capability_registry_lifecycle() -> None:
    registry = CapabilityRegistry()
    capability = object()

    registry.register("firmware", capability)

    assert registry.get("firmware") is capability
    assert registry.list_capabilities() == ["firmware"]
    assert registry.unregister("firmware") is capability
    with pytest.raises(KeyError):
        registry.get("firmware")


def test_capability_registry_rejects_duplicate_names() -> None:
    registry = CapabilityRegistry()
    registry.register("firmware", object())

    with pytest.raises(ValueError, match="already registered"):
        registry.register("firmware", object())
