from __future__ import annotations

from .service import ToolAdapterService


def create_tool_adapter_service(
    *, build_port=None, flash_port=None
) -> ToolAdapterService:
    return ToolAdapterService(build_port=build_port, flash_port=flash_port)


__all__ = ["create_tool_adapter_service"]
