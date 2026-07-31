"""Narrow facade for the Engineering Generation Runtime."""

from __future__ import annotations

from embedded_copilot.engineering_generation.contracts import EngineeringGenerationPort


class EngineeringGenerationRuntime:
    """Expose only the public generation port."""

    __slots__ = ("__generation_port",)

    def __init__(self, generation_port: EngineeringGenerationPort) -> None:
        self.__generation_port = generation_port

    @classmethod
    def _compose(
        cls, generation_port: EngineeringGenerationPort
    ) -> EngineeringGenerationRuntime:
        return cls(generation_port)

    def generation_port(self) -> EngineeringGenerationPort:
        return self.__generation_port
