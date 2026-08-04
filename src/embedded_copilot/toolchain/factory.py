from __future__ import annotations

from .contracts import BuildPort, BuildResult
from .exceptions import ToolchainUnavailable
from .service import ToolchainService


class UnavailableBuildPort(BuildPort):
    def build(self, workspace_reference: str) -> BuildResult:
        raise ToolchainUnavailable()


def create_toolchain_service(port: BuildPort | None = None) -> ToolchainService:
    return ToolchainService(port or UnavailableBuildPort())


__all__ = ["UnavailableBuildPort", "create_toolchain_service"]
