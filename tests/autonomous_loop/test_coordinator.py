from __future__ import annotations

from datetime import UTC, datetime

from embedded_copilot.autonomous_loop.contracts import AutonomousLoopSnapshot
from embedded_copilot.autonomous_loop.service import LoopCoordinatorService
from embedded_copilot.memory_automation import (
    MemorySourceKind,
    MemoryType,
    VersionMemoryInput,
)
from embedded_copilot.memory_automation.contracts import MemorySourceProjection


class _State:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.saved = []

    def get_snapshot(self, project_id):
        return self.snapshot

    def save_snapshot(self, snapshot):
        self.saved.append(snapshot)
        self.snapshot = snapshot


def test_coordinator_requires_injected_state_port() -> None:
    assert LoopCoordinatorService
    assert AutonomousLoopSnapshot


def test_loop_result_memory_type_is_an_explicit_projection() -> None:
    value = VersionMemoryInput(
        source=MemorySourceProjection(
            source_type=MemorySourceKind.ENGINEERING_LOOP_RESULT,
            source_id="loop-1",
            source_reference="loop:loop-1",
            source_fingerprint="sha256:" + "1" * 64,
            observed_at=datetime(2026, 8, 1, tzinfo=UTC),
        ),
        summary="Validation result requires review.",
        memory_type=MemoryType.ENGINEERING_LOOP_RESULT,
    )
    assert value.memory_type is MemoryType.ENGINEERING_LOOP_RESULT
