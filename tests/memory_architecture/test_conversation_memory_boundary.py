from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from embedded_copilot.conversation_memory import (
    ConversationSnapshot,
    ConversationTurn,
    MemoryCandidateStatus,
    MemoryType,
    create_conversation_memory,
)


ROOT = Path("src/embedded_copilot/conversation_memory")
FORBIDDEN_ROOTS = {
    "asyncio", "httpx", "os", "pathlib", "requests", "socket", "subprocess",
    "urllib", "uuid", "websockets",
}
FORBIDDEN_PREFIXES = (
    "embedded_copilot.agents",
    "embedded_copilot.api",
    "embedded_copilot.build",
    "embedded_copilot.device",
    "embedded_copilot.engineering_memory",
    "embedded_copilot.flash",
    "embedded_copilot.runtime",
    "embedded_copilot.tool",
)


def test_conversation_snapshot_only_produces_pending_candidate() -> None:
    snapshot = ConversationSnapshot(
        project_id="project-1",
        session_id="session-1",
        captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        turns=(
            ConversationTurn(
                turn_id="turn-1",
                role="USER",
                content_summary="The architecture decision is to keep the UART boundary explicit.",
                references=("design:uart",),
            ),
        ),
    )

    candidate = create_conversation_memory().extract(snapshot)

    assert candidate is not None
    assert candidate.memory_type is MemoryType.ARCHITECTURE
    assert candidate.status is MemoryCandidateStatus.PENDING_REVIEW
    assert candidate.project_id == "project-1"
    assert candidate.fingerprint.startswith("sha256:")


def test_non_engineering_conversation_does_not_create_candidate() -> None:
    snapshot = ConversationSnapshot(
        project_id="project-1",
        session_id="session-1",
        captured_at=datetime(2026, 8, 1, tzinfo=UTC),
        turns=(
            ConversationTurn(
                turn_id="turn-1",
                role="USER",
                content_summary="Please summarize this greeting.",
            ),
        ),
    )
    assert create_conversation_memory().extract(snapshot) is None


def test_conversation_memory_package_has_no_execution_or_memory_store_dependency() -> None:
    for path in ROOT.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                modules = ()
            for module in modules:
                assert module.split(".", 1)[0] not in FORBIDDEN_ROOTS
                assert not module.startswith(FORBIDDEN_PREFIXES)
        lowered = source.casefold()
        for token in ("engineeringmemorystore", "memory_automation", "build", "flash", "workspace"):
            assert token not in lowered, (path, token)
