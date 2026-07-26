from __future__ import annotations

from embedded_copilot.vision_runtime.contracts import VisionPort


class VisionRuntime:
    __slots__ = ("_vision",)

    def __init__(self, vision: VisionPort) -> None:
        raise TypeError("VisionRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, vision: VisionPort) -> "VisionRuntime":
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_vision", vision)
        return runtime

    def vision_port(self) -> VisionPort:
        return self._vision
