from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from embedded_copilot.conversation_memory import (
    ConversationMemoryCandidate,
    ConversationMemoryService,
    ConversationSnapshot,
    ConversationTurn,
    MemoryCandidateStatus,
)
from embedded_copilot.memory_automation import (
    MemoryApprovalProjection,
    MemoryPromotionService,
)
from embedded_copilot.memory_automation.exceptions import MemoryApprovalRejected


NOW = datetime(2026, 8, 1, tzinfo=UTC)
SOURCE_ROOT = Path(__file__).parents[2] / "src" / "embedded_copilot"


class _EngineeringMemorySpy:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def execute(self, request: object) -> object:
        self.calls.append(request)
        raise AssertionError("rejected promotion reached Engineering Memory")


def _snapshot() -> ConversationSnapshot:
    return ConversationSnapshot(
        project_id="project-1",
        session_id="session-1",
        captured_at=NOW,
        turns=(
            ConversationTurn(
                turn_id="turn-1",
                role="USER",
                content_summary="Decision: use the explicit runtime boundary.",
                references=("decision:runtime-boundary",),
            ),
        ),
    )


def test_conversation_service_only_creates_pending_candidate() -> None:
    candidate = ConversationMemoryService().extract(_snapshot())

    assert isinstance(candidate, ConversationMemoryCandidate)
    assert candidate.status is MemoryCandidateStatus.PENDING_REVIEW


def test_rejected_or_mismatched_approval_never_calls_engineering_memory() -> None:
    candidate = ConversationMemoryService().extract(_snapshot())
    assert candidate is not None
    spy = _EngineeringMemorySpy()

    with pytest.raises(MemoryApprovalRejected):
        MemoryPromotionService(spy).promote(
            candidate,
            MemoryApprovalProjection(
                memory_id=candidate.candidate_id,
                candidate_fingerprint="sha256:" + "0" * 64,
                reviewer="reviewer-1",
                decision="APPROVED",
                reviewed_at=NOW,
            ),
        )

    with pytest.raises(MemoryApprovalRejected):
        MemoryPromotionService(spy).promote(
            candidate,
            MemoryApprovalProjection(
                memory_id=candidate.candidate_id,
                candidate_fingerprint=candidate.fingerprint,
                reviewer="reviewer-1",
                decision="REJECTED",
                reviewed_at=NOW,
            ),
        )

    assert spy.calls == []


def test_memory_layers_do_not_have_reverse_production_imports() -> None:
    forbidden_edges = {
        "conversation_memory/service.py": (
            "embedded_copilot.engineering_memory",
            "embedded_copilot.memory_automation",
        ),
        "knowledge_evolution/service.py": (
            "embedded_copilot.memory_automation",
            "embedded_copilot.conversation_memory",
        ),
        "knowledge_writer/writer.py": ("embedded_copilot.conversation_memory",),
    }

    for relative, forbidden in forbidden_edges.items():
        path = SOURCE_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert imported.isdisjoint(forbidden), (path, imported & set(forbidden))
