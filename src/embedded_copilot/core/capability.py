from __future__ import annotations


class CapabilityRegistry:
    """In-memory registry for capability implementations or factories."""

    def __init__(self) -> None:
        self._capabilities: dict[str, object] = {}

    def register(self, name: str, capability: object) -> None:
        key = self._normalize_name(name)
        if key in self._capabilities:
            raise ValueError(f"capability already registered: {key}")
        self._capabilities[key] = capability

    def unregister(self, name: str) -> object:
        return self._capabilities.pop(self._normalize_name(name))

    def get(self, name: str) -> object:
        return self._capabilities[self._normalize_name(name)]

    def list_capabilities(self) -> list[str]:
        return list(self._capabilities)

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("capability name must not be empty")
        return normalized
