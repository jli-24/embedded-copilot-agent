"""Backward-compatible API dependency imports."""

from embedded_copilot.services.runtime import (
    RuntimeComponents,
    RuntimeInitializationError,
    build_runtime,
)

__all__ = [
    "RuntimeComponents",
    "RuntimeInitializationError",
    "build_runtime",
]
