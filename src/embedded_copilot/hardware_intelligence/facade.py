"""Public facade for the Hardware Intelligence Runtime."""

from embedded_copilot.hardware_intelligence.contracts import HardwareIntelligencePort


class HardwareIntelligenceRuntime:
    """Facade exposing only the stable hardware intelligence port."""

    __slots__ = ("__hardware_port",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use the composition factory")

    @classmethod
    def _compose(
        cls, hardware_port: HardwareIntelligencePort
    ) -> "HardwareIntelligenceRuntime":
        runtime = object.__new__(cls)
        runtime.__hardware_port = hardware_port
        return runtime

    def hardware_port(self) -> HardwareIntelligencePort:
        return self.__hardware_port
