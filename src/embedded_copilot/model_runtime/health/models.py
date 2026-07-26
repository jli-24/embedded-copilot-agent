from __future__ import annotations

from typing import Literal

from embedded_copilot.schemas.result import ContractModel


class ModelStatusResponse(ContractModel):
    provider: str
    status: Literal["available", "unavailable"]
    capabilities: tuple[str, ...]
    model: str | None
