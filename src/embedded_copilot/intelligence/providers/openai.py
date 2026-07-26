from __future__ import annotations

from embedded_copilot.intelligence.providers.unavailable import (
    UnavailableModelProvider,
)


class OpenAIModelProvider(UnavailableModelProvider):
    provider_id = "openai"
