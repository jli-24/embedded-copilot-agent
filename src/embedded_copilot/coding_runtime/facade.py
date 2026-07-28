from __future__ import annotations

from embedded_copilot.coding_runtime.contracts import CodingIntelligencePort


class CodingRuntime:
    __slots__ = ("_coding_port",)

    def __init__(self, coding_port: CodingIntelligencePort) -> None:
        raise TypeError("CodingRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, coding_port: CodingIntelligencePort) -> "CodingRuntime":
        if not isinstance(coding_port, CodingIntelligencePort):
            raise TypeError("coding port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_coding_port", coding_port)
        return runtime

    def coding_port(self) -> CodingIntelligencePort:
        return self._coding_port
