"""Backward-compatible Runtime composition facade."""

from embedded_copilot.services.canonical_runtime import (
    CANONICAL_RUNTIME_AGENT_NAMES,
    CANONICAL_RUNTIME_AGENT_TYPES,
    CANONICAL_RUNTIME_ROUTER,
    RuntimeComponents,
    RuntimeInitializationError,
    build_canonical_runtime,
)
from embedded_copilot.services.legacy_runtime import (
    build_legacy_runtime,
    build_legacy_runtime as build_analysis_service,
)

build_runtime = build_canonical_runtime

__all__ = (
    "CANONICAL_RUNTIME_AGENT_NAMES",
    "CANONICAL_RUNTIME_AGENT_TYPES",
    "CANONICAL_RUNTIME_ROUTER",
    "RuntimeComponents",
    "RuntimeInitializationError",
    "build_analysis_service",
    "build_canonical_runtime",
    "build_legacy_runtime",
    "build_runtime",
)
