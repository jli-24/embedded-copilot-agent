from __future__ import annotations

from embedded_copilot.intelligence.providers.unavailable import (
    UnavailableModelProvider,
)


class OllamaModelProvider(UnavailableModelProvider):
    provider_id = "ollama"
