from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.memory_automation import (
    MemorySourceKind,
    MemorySourceProjection,
    MemoryType,
    VersionMemoryInput,
    project_candidate,
)


def _source() -> MemorySourceProjection:
    return MemorySourceProjection(
        source_type=MemorySourceKind.BUILD_OBSERVATION,
        source_id="build-1",
        source_reference="build:1",
        source_fingerprint="sha256:" + "a" * 64,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_projection_is_deterministic_and_frozen() -> None:
    value = VersionMemoryInput(
        source=_source(),
        summary="Build passed",
        memory_type=MemoryType.BUILD_OBSERVATION,
    )
    first = project_candidate(value)
    second = project_candidate(value)
    assert first == second
    with pytest.raises(ValidationError):
        first.summary = "changed"
    assert first.memory_id.startswith("memory-")


def test_raw_sensitive_projection_is_rejected() -> None:
    with pytest.raises(ValidationError):
        VersionMemoryInput(source=_source(), summary="api_key=secret")


def test_collections_are_tuple_only() -> None:
    with pytest.raises(ValidationError):
        VersionMemoryInput(source=_source(), summary="safe", tags=["tag"])  # type: ignore[arg-type]

