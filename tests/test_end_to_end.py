from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import chromadb
import pytest

from embedded_copilot.api.dependencies import RuntimeComponents, build_runtime
from embedded_copilot.schemas.result import DebugResult, FirmwareResult, KnowledgeResult
from embedded_copilot.services.config import Settings


@pytest.fixture(scope="module")
def runtime() -> RuntimeComponents:
    settings = Settings(
        knowledge_dir=Path("knowledge"),
        collection_name="e2e_foundation",
        embedding_dimension=64,
        chunk_size=400,
        chunk_overlap=40,
        retrieval_score_threshold=0.05,
        _env_file=None,
    )
    return build_runtime(settings, chroma_client=chromadb.EphemeralClient())


def test_knowledge_request_completes_cited_rag_loop(
    runtime: RuntimeComponents,
) -> None:
    response = asyncio.run(
        runtime.service.chat("ESP32如何配置SPI？", trace_id="trace-knowledge")
    )

    assert response.agents_used == ["knowledge"]
    assert isinstance(response.result, KnowledgeResult)
    assert response.result.insufficient_context is False
    assert response.sources
    assert all(citation.filename and citation.chunk_id for citation in response.sources)
    assert "Sources:" in response.answer


def test_firmware_request_returns_structured_unverified_code(
    runtime: RuntimeComponents,
) -> None:
    response = asyncio.run(
        runtime.service.chat(
            "生成ESP32 FreeRTOS LED任务",
            trace_id="trace-firmware",
        )
    )

    assert response.agents_used == ["firmware"]
    assert isinstance(response.result, FirmwareResult)
    assert "#include <stdbool.h>" in response.result.code
    assert "CONFIG_LED_GPIO" in response.result.code
    assert any("hardware" in item.lower() for item in response.result.limitations)


def test_debug_request_returns_evidence_labeled_report(
    runtime: RuntimeComponents,
) -> None:
    response = asyncio.run(
        runtime.service.chat(
            "分析这个Guru Meditation Error: LoadProhibited\n"
            "Backtrace: 0x40081234:0x3ffb1230",
            trace_id="trace-debug",
        )
    )

    assert response.agents_used == ["debug"]
    assert isinstance(response.result, DebugResult)
    assert response.result.evidence
    assert response.result.root_cause
    assert response.result.confidence == "medium"
    assert "Evidence:" in response.answer
    assert "Root Cause:" in response.answer


def test_workflow_emits_traceable_events(
    runtime: RuntimeComponents,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    asyncio.run(
        runtime.service.chat("ESP32如何配置SPI？", trace_id="trace-events")
    )

    records = [
        record
        for record in caplog.records
        if getattr(record, "trace_id", None) == "trace-events"
    ]
    event_names = [getattr(record, "event_name", None) for record in records]
    assert event_names == [
        "workflow_start",
        "agent_selected",
        "tool_called",
        "tool_completed",
        "workflow_completed",
    ]
    assert all(getattr(record, "trace_id", None) == "trace-events" for record in records)


def test_unapproved_future_roadmap_packages_do_not_exist() -> None:
    package_root = Path("src/embedded_copilot")

    for forbidden in ("competition", "edge_ai", "computer_use"):
        assert not (package_root / forbidden).exists()
