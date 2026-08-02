from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.ai_runtime import (
    AIModelUnavailable,
    EngineeringChatContext,
    EngineeringChatRequest,
    KnowledgeEvidenceProjection,
    canonical_ai_json,
    create_ai_runtime,
    engineering_chat_context_fingerprint,
    engineering_chat_request_fingerprint,
    knowledge_evidence_fingerprint,
)
from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.engineering_events import EngineeringEventType
from embedded_copilot.intelligence.models import ModelResponse


def _context() -> EngineeringChatContext:
    values = dict(
        project_id="project-1",
        project_summary="ESP32-S3 smart camera engineering workspace",
        current_stage="ARCHITECTURE",
        reference_ids=("requirement-1",),
        decision_summaries=("CAMERA_INTERFACE_PENDING",),
        workspace_fingerprint="sha256:" + "1" * 64,
    )
    return EngineeringChatContext(
        **values,
        fingerprint=engineering_chat_context_fingerprint(**values),
    )


def _request() -> EngineeringChatRequest:
    values = dict(
        request_id="chat-1",
        project_id="project-1",
        message="Recommend the next safe architecture decision.",
        context=_context(),
        requested_at=datetime(2026, 8, 12, 8, 0, tzinfo=UTC),
    )
    return EngineeringChatRequest(
        **values,
        fingerprint=engineering_chat_request_fingerprint(**values),
    )


def _knowledge() -> KnowledgeEvidenceProjection:
    values = dict(
        evidence_id="evidence-1",
        summary="ESP32-S3 supports the required camera interface.",
        source_references=("datasheet:esp32-s3:camera",),
        confidence=1.0,
    )
    return KnowledgeEvidenceProjection(
        **values,
        fingerprint=knowledge_evidence_fingerprint(**values),
    )


def _model_text() -> str:
    return json.dumps(
        {
            "requirement_analysis": "The camera and low-power goals need explicit budgets.",
            "architecture_recommendation": "Keep capture, transport, and power boundaries separate.",
            "hardware_suggestion": "Review the explicit ESP32-S3 camera interface evidence.",
            "risk_analysis": "Power budget and camera timing remain unverified.",
            "next_action": "Request verified power and timing constraints before execution.",
            "reference_ids": ["datasheet:esp32-s3:camera"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _reasoning_output(text: str = "") -> ReasoningOutput:
    return ReasoningOutput(
        response=ModelResponse(
            text=text or _model_text(),
            source="ollama",
        )
    )


@dataclass
class ReasoningFake:
    outputs: list[object]
    calls: list[dict[str, object]] = field(default_factory=list)

    async def reason(self, **values: object) -> ReasoningOutput:
        self.calls.append(values)
        current = self.outputs.pop(0)
        if isinstance(current, Exception):
            raise current
        assert type(current) is ReasoningOutput
        return current


@dataclass
class KnowledgeFake:
    evidence: tuple[KnowledgeEvidenceProjection, ...]
    calls: list[tuple[str, str]] = field(default_factory=list)
    failure: Exception | None = None

    def retrieve(
        self,
        *,
        request_id: str,
        query_summary: str,
    ) -> tuple[KnowledgeEvidenceProjection, ...]:
        self.calls.append((request_id, query_summary))
        if self.failure is not None:
            raise self.failure
        return tuple(item.model_copy(deep=True) for item in self.evidence)


def test_chat_contract_is_frozen_strict_and_deterministic() -> None:
    request = _request()

    assert canonical_ai_json(request) == canonical_ai_json(_request())
    assert hash(request) == hash(_request())
    with pytest.raises(ValidationError):
        request.message = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringChatRequest.model_validate(
            {**request.model_dump(), "provider": "ollama"}
        )
    with pytest.raises(ValidationError):
        _context().model_copy(update={"current_stage": "possible stage"}).model_validate(
            _context().model_copy(update={"current_stage": "possible stage"})
        )


def test_chat_projects_structured_response_and_safe_events() -> None:
    reasoning = ReasoningFake([_reasoning_output()])
    knowledge = KnowledgeFake((_knowledge(),))
    port = create_ai_runtime(
        reasoning_port=reasoning,
        knowledge_port=knowledge,
        max_attempts=2,
    ).engineering_chat_port()
    request = _request()
    before = request.model_dump(mode="json")

    response = asyncio.run(port.chat(request))

    assert response.requirement_analysis.startswith("The camera")
    assert response.next_action.startswith("Request verified")
    assert response.reference_ids == ("datasheet:esp32-s3:camera",)
    assert tuple(event.sequence for event in response.events) == (1, 2, 3, 4)
    assert tuple(event.event_type for event in response.events) == (
        EngineeringEventType.AGENT_STARTED,
        EngineeringEventType.AGENT_PROGRESS,
        EngineeringEventType.AGENT_PROGRESS,
        EngineeringEventType.COMPLETED,
    )
    assert len(reasoning.calls) == 1
    assert knowledge.calls == [("chat-1", request.message)]
    assert request.model_dump(mode="json") == before
    serialized = response.model_dump(mode="json")
    assert "ollama" not in str(serialized).lower()
    assert "workspace_fingerprint" not in serialized


def test_chat_retries_model_only_to_fixed_limit() -> None:
    reasoning = ReasoningFake([RuntimeError("provider secret"), _reasoning_output()])
    knowledge = KnowledgeFake((_knowledge(),))
    port = create_ai_runtime(
        reasoning_port=reasoning,
        knowledge_port=knowledge,
        max_attempts=2,
    ).engineering_chat_port()

    result = asyncio.run(port.chat(_request()))

    assert result.next_action.startswith("Request verified")
    assert len(reasoning.calls) == 2
    assert len(knowledge.calls) == 1


def test_chat_model_failure_is_sanitized_after_attempt_limit() -> None:
    reasoning = ReasoningFake(
        [RuntimeError("api_key=secret"), RuntimeError("C:/private/model.log")]
    )
    port = create_ai_runtime(
        reasoning_port=reasoning,
        knowledge_port=None,
        max_attempts=2,
    ).engineering_chat_port()

    with pytest.raises(AIModelUnavailable) as captured:
        asyncio.run(port.chat(_request()))

    assert str(captured.value) == "engineering AI is unavailable"
    assert "secret" not in str(captured.value)
    assert len(reasoning.calls) == 2


def test_knowledge_failure_degrades_to_model_context_without_retry() -> None:
    reasoning = ReasoningFake([_reasoning_output()])
    knowledge = KnowledgeFake((), failure=RuntimeError("database password=secret"))
    port = create_ai_runtime(
        reasoning_port=reasoning,
        knowledge_port=knowledge,
        max_attempts=1,
    ).engineering_chat_port()

    response = asyncio.run(port.chat(_request()))

    assert len(knowledge.calls) == 1
    assert len(reasoning.calls) == 1
    assert response.events[1].status == "UNAVAILABLE"
    assert "secret" not in canonical_ai_json(response)


def test_malformed_model_output_fails_closed() -> None:
    reasoning = ReasoningFake([_reasoning_output("not-json")])
    port = create_ai_runtime(
        reasoning_port=reasoning,
        knowledge_port=None,
        max_attempts=1,
    ).engineering_chat_port()

    with pytest.raises(AIModelUnavailable):
        asyncio.run(port.chat(_request()))
