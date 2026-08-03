from __future__ import annotations

from .service import EngineeringIntelligenceService


class EngineeringIntelligenceRuntime:
    __slots__ = ("_service",)

    def __init__(self, service: EngineeringIntelligenceService) -> None:
        raise TypeError("EngineeringIntelligenceRuntime must be created by its factory")

    @classmethod
    def _compose(
        cls, service: EngineeringIntelligenceService
    ) -> "EngineeringIntelligenceRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_service", service)
        return runtime

    def intelligence_port(self) -> EngineeringIntelligenceService:
        return self._service


def create_engineering_intelligence(
    *,
    knowledge_port: object | None = None,
    memory_port: object | None = None,
    datasheet_port: object | None = None,
    web_port: object | None = None,
) -> EngineeringIntelligenceRuntime:
    return EngineeringIntelligenceRuntime._compose(
        EngineeringIntelligenceService(
            knowledge_port=knowledge_port,
            memory_port=memory_port,
            datasheet_port=datasheet_port,
            web_port=web_port,
        )
    )
