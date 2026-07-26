from __future__ import annotations

import httpx

from embedded_copilot.multimodal.context import AttachmentBindingRepository
from embedded_copilot.vision_runtime.composition.config import (
    VisionSettingsSource,
    load_vision_runtime_config,
)
from embedded_copilot.vision_runtime.facade import VisionRuntime
from embedded_copilot.vision_runtime.gateway import ReferenceVisionPort
from embedded_copilot.vision_runtime.providers import (
    OllamaVisionProvider,
    UnavailableVisionProvider,
    VisionProvider,
)
from embedded_copilot.vision_runtime.routing import (
    VisionProviderRegistry,
    VisionRouter,
)


def create_vision_runtime(
    settings: VisionSettingsSource,
    attachment_repository: AttachmentBindingRepository,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VisionRuntime:
    config = load_vision_runtime_config(settings)
    provider: VisionProvider
    if config.provider == "ollama":
        if config.base_url is None or config.model is None:
            raise ValueError("vision runtime configuration is invalid")
        provider = OllamaVisionProvider(
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            transport=transport,
        )
    else:
        provider = UnavailableVisionProvider()
    router = VisionRouter(VisionProviderRegistry((provider,)))
    port = ReferenceVisionPort(attachment_repository, router)
    return VisionRuntime._compose(port)
