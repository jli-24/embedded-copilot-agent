from __future__ import annotations

import pytest

from embedded_copilot.intelligence.models import ModelCapability
from embedded_copilot.model_runtime.registry import ProviderRegistry


class _Provider:
    def __init__(
        self,
        provider_id: str,
        capabilities: tuple[ModelCapability, ...],
    ) -> None:
        self.provider_id = provider_id
        self.supported_tasks = capabilities

    async def generate(self, request, model_input):
        raise AssertionError("not used")


def test_registry_preserves_registration_order_for_capability() -> None:
    first = _Provider("first-provider", (ModelCapability.CHAT,))
    second = _Provider(
        "second-provider",
        (ModelCapability.CHAT, ModelCapability.REASONING),
    )

    registry = ProviderRegistry((first, second))

    assert registry.for_capability(ModelCapability.CHAT) == (first, second)
    assert registry.for_capability(ModelCapability.REASONING) == (second,)
    assert registry.for_capability(ModelCapability.VISION) == ()


def test_registry_rejects_duplicate_provider_identifiers() -> None:
    with pytest.raises(ValueError, match="provider registry is invalid"):
        ProviderRegistry(
            (
                _Provider("same-provider", (ModelCapability.CHAT,)),
                _Provider("SAME-PROVIDER", (ModelCapability.CODE,)),
            )
        )
