from __future__ import annotations

from .contracts import ReasoningPort
from .service import ReasoningService


def create_reasoning_service(port: ReasoningPort) -> ReasoningService:
    return ReasoningService(port)


__all__ = ["create_reasoning_service"]
