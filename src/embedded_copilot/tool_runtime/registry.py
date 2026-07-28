from __future__ import annotations

from embedded_copilot.tool_runtime.ports import EngineeringToolPort


class _ToolRegistry:
    __slots__ = ("_entries",)

    def __init__(
        self,
        entries: tuple[tuple[str, EngineeringToolPort], ...],
    ) -> None:
        self._entries = entries

    def resolve(self, tool_name: str) -> EngineeringToolPort | None:
        for registered_name, tool in self._entries:
            if registered_name == tool_name:
                return tool
        return None
