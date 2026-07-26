from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.intelligence._validation import safe_identifier
from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import ModelCapability
from embedded_copilot.intelligence.providers.base import ModelProvider
from embedded_copilot.schemas.model import ModelTaskType


def validate_providers(
    providers: Sequence[ModelProvider],
) -> tuple[ModelProvider, ...]:
    validated: list[ModelProvider] = []
    identifiers: set[str] = set()
    for provider in providers:
        try:
            provider_id = safe_identifier(provider.provider_id, field="provider_id")
            tasks = _capabilities(provider.supported_tasks)
            generate = provider.generate
        except Exception as exc:
            raise ValueError("model provider configuration is invalid") from exc
        if (
            not isinstance(tasks, tuple)
            or not tasks
            or len(set(tasks)) != len(tasks)
            or not callable(generate)
            or provider_id.casefold() in identifiers
        ):
            raise ValueError("model provider configuration is invalid")
        identifiers.add(provider_id.casefold())
        validated.append(provider)
    return tuple(validated)


def select_provider(
    providers: Sequence[ModelProvider],
    capability: ModelCapability,
) -> ModelProvider:
    for provider in providers:
        if capability in _capabilities(provider.supported_tasks):
            return provider
    raise ModelProviderUnavailable("model provider is unavailable")


def _capabilities(
    tasks: object,
) -> tuple[ModelCapability, ...]:
    if not isinstance(tasks, tuple) or not tasks:
        raise ValueError("model provider configuration is invalid")
    try:
        return tuple(
            ModelCapability(task.value)
            for task in tasks
            if isinstance(task, (ModelCapability, ModelTaskType))
        )
    except ValueError:
        raise ValueError("model provider configuration is invalid") from None
