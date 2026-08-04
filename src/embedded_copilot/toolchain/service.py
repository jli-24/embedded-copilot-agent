from __future__ import annotations

import copy

from .contracts import BuildPort, BuildResult, validate_build_result
from .exceptions import BuildFailed, ToolchainUnavailable
from .models import identifier


class ToolchainService:
    __slots__ = ("_port",)

    def __init__(self, port: BuildPort) -> None:
        if not isinstance(port, BuildPort):
            raise TypeError("build port is invalid")
        self._port = port

    def build(self, workspace_reference: str) -> BuildResult:
        try:
            reference = identifier(workspace_reference, field="workspace_reference")
        except ValueError as error:
            raise ToolchainUnavailable() from error
        try:
            result = self._port.build(copy.deepcopy(reference))
            checked = validate_build_result(result)
        except ToolchainUnavailable:
            raise
        except Exception as error:
            raise BuildFailed() from error
        if checked.status.value == "FAILED":
            raise BuildFailed()
        return checked
