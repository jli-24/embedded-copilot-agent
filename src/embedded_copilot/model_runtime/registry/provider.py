from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from embedded_copilot.intelligence._validation import safe_identifier
from embedded_copilot.intelligence.models import ModelCapability
from embedded_copilot.model_runtime.providers.base import ModelProvider


@dataclass(frozen=True, slots=True)
class ProviderRegistry:
    _providers: tuple[ModelProvider, ...]

    def __init__(self, providers: Sequence[ModelProvider]) -> None:
        validated = _validate_providers(tuple(providers))
        object.__setattr__(self, "_providers", validated)

    def for_capability(
        self,
        capability: ModelCapability,
    ) -> tuple[ModelProvider, ...]:
        return tuple(
            provider
            for provider in self._providers
            if capability in provider.supported_tasks
        )


def _validate_providers(
    providers: tuple[ModelProvider, ...],
) -> tuple[ModelProvider, ...]:
    identifiers: set[str] = set()
    for provider in providers:
        try:
            provider_id = safe_identifier(provider.provider_id, field="provider_id")
            capabilities = provider.supported_tasks
            generate = provider.generate
        except Exception as error:
            raise ValueError("provider registry is invalid") from error
        normalized = provider_id.casefold()
        if (
            normalized in identifiers
            or not isinstance(capabilities, tuple)
            or not capabilities
            or len(set(capabilities)) != len(capabilities)
            or not all(isinstance(item, ModelCapability) for item in capabilities)
            or not callable(generate)
        ):
            raise ValueError("provider registry is invalid")
        identifiers.add(normalized)
    return providers
