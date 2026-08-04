from __future__ import annotations

from .espidf import BuildExecutorPort
from ..contracts import BuildPort, BuildResult, validate_build_result
from ..exceptions import ToolchainUnavailable


class PlatformIoBuildAdapter(BuildPort):
    def __init__(self, executor: BuildExecutorPort | None = None) -> None:
        self._executor = executor

    def build(self, workspace_reference: str) -> BuildResult:
        if self._executor is None:
            raise ToolchainUnavailable()
        try:
            return validate_build_result(self._executor.build(workspace_reference))
        except ToolchainUnavailable:
            raise
        except Exception as error:
            raise ToolchainUnavailable() from error


__all__ = ["PlatformIoBuildAdapter"]
