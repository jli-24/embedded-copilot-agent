from __future__ import annotations

from .contracts import EngineeringCompletionPort
from .service import EngineeringCompletionService


def create_engineering_completion_service(
    port: EngineeringCompletionPort,
) -> EngineeringCompletionService:
    return EngineeringCompletionService(port)


__all__ = ["create_engineering_completion_service"]
