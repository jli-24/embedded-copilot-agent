from __future__ import annotations

import pytest

from embedded_copilot.knowledge.models import KnowledgeQuery
from embedded_copilot.supervisor.knowledge_query import KnowledgeQueryBuilder
from embedded_copilot.supervisor.models import SupervisorTask


def test_builder_creates_canonical_camera_query_without_raw_request() -> None:
    task = SupervisorTask(
        request="Design an ESP32 camera board with confidential-project-marker",
        required_agents=["FirmwareAgent", "HardwareAgent"],
    )

    query = KnowledgeQueryBuilder().build(task)

    assert isinstance(query, KnowledgeQuery)
    assert query.query == "ESP32 Camera OV2640 GPIO Power firmware hardware"
    assert query.sources == []
    assert query.top_k == 4
    assert query.metadata == {
        "topic": "ESP32 Camera",
        "keywords": ["ESP32", "Camera", "OV2640", "GPIO", "Power"],
        "domains": ["firmware", "hardware"],
    }
    assert "confidential-project-marker" not in query.model_dump_json()


def test_builder_uses_stable_fallback_and_does_not_mutate_task() -> None:
    task = SupervisorTask(request="unclassified request", metadata={"nested": []})
    before = task.model_dump(mode="python")

    first = KnowledgeQueryBuilder().build(task)
    second = KnowledgeQueryBuilder().build(task)

    assert task.model_dump(mode="python") == before
    assert first == second
    assert first.query == "Embedded Engineering"
    assert first.metadata == {
        "topic": "Embedded Engineering",
        "keywords": [],
        "domains": [],
    }


def test_builder_rejects_invalid_input() -> None:
    with pytest.raises(TypeError, match="SupervisorTask"):
        KnowledgeQueryBuilder().build("firmware")  # type: ignore[arg-type]
