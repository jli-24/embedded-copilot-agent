from __future__ import annotations

from embedded_copilot.knowledge.intelligence.ports import (
    KnowledgeIntelligencePort,
)


class KnowledgeIntelligenceRuntime:
    __slots__ = ("_knowledge_port",)

    def __init__(self) -> None:
        raise TypeError(
            "KnowledgeIntelligenceRuntime must be created by its factory"
        )

    @classmethod
    def _compose(
        cls,
        knowledge_port: KnowledgeIntelligencePort,
    ) -> KnowledgeIntelligenceRuntime:
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_knowledge_port", knowledge_port)
        return runtime

    def knowledge_port(self) -> KnowledgeIntelligencePort:
        return self._knowledge_port
