from __future__ import annotations

import httpx

from embedded_copilot.model_runtime.composition.config import (
    ModelSettingsSource,
    load_model_runtime_config,
)
from embedded_copilot.model_runtime.facade import ModelRuntime
from embedded_copilot.model_runtime.gateway.model import ModelGateway
from embedded_copilot.model_runtime.gateway.reasoning import GatewayReasoningPort
from embedded_copilot.model_runtime.health.status import (
    OllamaStatusPort,
    UnavailableStatusPort,
)
from embedded_copilot.model_runtime.providers.base import ModelProvider
from embedded_copilot.model_runtime.providers.ollama import OllamaProvider
from embedded_copilot.model_runtime.registry import ProviderRegistry
from embedded_copilot.model_runtime.routing import ModelRouter


def create_model_runtime(
    settings: ModelSettingsSource,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ModelRuntime:
    config = load_model_runtime_config(settings)
    providers: tuple[ModelProvider, ...] = ()
    status = UnavailableStatusPort()
    if config.provider == "ollama":
        if config.base_url is None or config.model is None:
            raise ValueError("model runtime configuration is invalid")
        providers = (
            OllamaProvider(
                base_url=config.base_url,
                model=config.model,
                timeout_seconds=config.timeout_seconds,
                transport=transport,
            ),
        )
        status = OllamaStatusPort(
            config.base_url,
            config.model,
            config.timeout_seconds,
            transport,
        )
    registry = ProviderRegistry(providers)
    router = ModelRouter(registry)
    gateway = ModelGateway(router)
    return ModelRuntime._compose(GatewayReasoningPort(gateway), status)
