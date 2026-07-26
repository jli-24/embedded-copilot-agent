from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.datasheet_runtime.contracts.models import (
    DatasheetRequest,
    DatasheetResponse,
)


@runtime_checkable
class DatasheetIntelligencePort(Protocol):
    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse: ...
