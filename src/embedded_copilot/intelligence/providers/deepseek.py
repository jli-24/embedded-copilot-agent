from __future__ import annotations

from embedded_copilot.intelligence.providers.unavailable import (
    UnavailableModelProvider,
)


class DeepSeekModelProvider(UnavailableModelProvider):
    provider_id = "deepseek"
