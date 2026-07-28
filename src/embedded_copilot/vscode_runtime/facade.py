from __future__ import annotations

from embedded_copilot.vscode_runtime.ports import VSCodePort


class VSCodeRuntime:
    __slots__ = ("_vscode_port",)

    def __init__(self, vscode_port: VSCodePort) -> None:
        raise TypeError("VSCodeRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, vscode_port: VSCodePort) -> "VSCodeRuntime":
        if not isinstance(vscode_port, VSCodePort):
            raise TypeError("vscode port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_vscode_port", vscode_port)
        return runtime

    def vscode_port(self) -> VSCodePort:
        return self._vscode_port
