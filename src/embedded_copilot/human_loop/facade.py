"""Narrow facade for the Human Loop Runtime."""

from __future__ import annotations

from embedded_copilot.human_loop.contracts import HumanLoopPort


class HumanLoopRuntime:
    """Expose only the public human-loop port."""

    __slots__ = ("__human_loop_port",)

    def __init__(self, human_loop_port: HumanLoopPort) -> None:
        self.__human_loop_port = human_loop_port

    @classmethod
    def _compose(cls, human_loop_port: HumanLoopPort) -> HumanLoopRuntime:
        return cls(human_loop_port)

    def human_loop_port(self) -> HumanLoopPort:
        return self.__human_loop_port
