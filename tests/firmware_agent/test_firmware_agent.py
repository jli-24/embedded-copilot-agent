from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.ai_runtime import (
    EngineeringChatContext,
    KnowledgeEvidenceProjection,
    engineering_chat_context_fingerprint,
    knowledge_evidence_fingerprint,
)
from embedded_copilot.conversation.models import ReasoningOutput
from embedded_copilot.engineering_events import EngineeringEventType
from embedded_copilot.firmware_agent import (
    FirmwareArtifactType,
    FirmwareGenerationRejected,
    FirmwareGenerationRequest,
    FirmwarePlatform,
    FirmwareProposal,
    create_firmware_agent,
    firmware_generation_request_fingerprint,
)
from embedded_copilot.intelligence.models import ModelResponse

_TIME = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)


def _context() -> EngineeringChatContext:
    values = {
        "project_id": "project-1",
        "project_summary": "ESP32-S3 camera with WiFi transport",
        "current_stage": "FIRMWARE",
        "reference_ids": ("requirement-1",),
        "decision_summaries": ("ESP_IDF_SELECTED",),
        "workspace_fingerprint": "sha256:" + "1" * 64,
    }
    return EngineeringChatContext(
        **values,
        fingerprint=engineering_chat_context_fingerprint(**values),
    )


def _knowledge() -> KnowledgeEvidenceProjection:
    values = {
        "evidence_id": "evidence-1",
        "summary": "ESP-IDF component boundaries are required.",
        "source_references": ("datasheet:esp32-s3",),
        "confidence": 1.0,
    }
    return KnowledgeEvidenceProjection(
        **values,
        fingerprint=knowledge_evidence_fingerprint(**values),
    )


def _request() -> FirmwareGenerationRequest:
    values = {
        "request_id": "firmware-1",
        "context": _context(),
        "knowledge": (_knowledge(),),
        "platform": FirmwarePlatform.ESP_IDF,
        "requested_at": _TIME,
    }
    return FirmwareGenerationRequest(
        **values,
        fingerprint=firmware_generation_request_fingerprint(**values),
    )


def _reasoning_output(*, path: str = "main/main.c") -> ReasoningOutput:
    text = json.dumps(
        {
            "files": [
                {
                    "logical_path": "CMakeLists.txt",
                    "purpose": "BUILD_ENTRY",
                    "content": "cmake_minimum_required(VERSION 3.16)\nproject(camera_demo)\n",
                },
                {
                    "logical_path": path,
                    "purpose": "APPLICATION_ENTRY",
                    "content": "#include <stdio.h>\nvoid app_main(void) { puts(\"proposal\"); }\n",
                },
            ]
        },
        sort_keys=True,
    )
    return ReasoningOutput(response=ModelResponse(text=text, source="ollama"))


@dataclass
class ReasoningFake:
    output: ReasoningOutput | Exception
    calls: list[dict[str, object]] = field(default_factory=list)

    async def reason(self, **values: object) -> ReasoningOutput:
        self.calls.append(values)
        if isinstance(self.output, Exception):
            raise self.output
        return self.output.model_copy(deep=True)


def test_firmware_contract_is_strict_frozen_and_tuple_only() -> None:
    request = _request()

    with pytest.raises(ValidationError):
        request.request_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        FirmwareGenerationRequest.model_validate(
            {**request.model_dump(), "provider": "ollama"}
        )
    with pytest.raises(ValidationError):
        FirmwareGenerationRequest.model_validate(
            {**request.model_dump(), "knowledge": [_knowledge()]}
        )


def test_agent_generates_safe_artifacts_and_event_without_mutating_input() -> None:
    reasoning = ReasoningFake(_reasoning_output())
    port = create_firmware_agent(reasoning_port=reasoning).firmware_agent_port()
    request = _request()
    before = request.model_dump(mode="json")

    proposal = asyncio.run(port.generate(request))

    assert type(proposal) is FirmwareProposal
    assert tuple(item.logical_path for item in proposal.files) == (
        "CMakeLists.txt",
        "main/main.c",
    )
    assert tuple(item.artifact_type for item in proposal.artifacts) == (
        FirmwareArtifactType.FIRMWARE_SOURCE,
        FirmwareArtifactType.BUILD_CONFIG,
        FirmwareArtifactType.PROJECT_STRUCTURE,
    )
    assert proposal.candidate_semantics == "unverified"
    assert proposal.review_required is True
    assert proposal.event.event_type is EngineeringEventType.ARTIFACT_CREATED
    assert proposal.source_workspace_fingerprint == request.context.workspace_fingerprint
    assert len(reasoning.calls) == 1
    assert request.model_dump(mode="json") == before


def test_agent_is_deterministic_and_rejects_unsafe_logical_path() -> None:
    request = _request()
    first = asyncio.run(
        create_firmware_agent(
            reasoning_port=ReasoningFake(_reasoning_output())
        ).firmware_agent_port().generate(request)
    )
    second = asyncio.run(
        create_firmware_agent(
            reasoning_port=ReasoningFake(_reasoning_output())
        ).firmware_agent_port().generate(request)
    )

    assert first == second
    assert first.fingerprint == second.fingerprint
    with pytest.raises(Exception, match="firmware generation was rejected"):
        asyncio.run(
            create_firmware_agent(
                reasoning_port=ReasoningFake(_reasoning_output(path="../secret.c"))
            ).firmware_agent_port().generate(request)
        )


def test_reasoning_failure_is_sanitized() -> None:
    agent = create_firmware_agent(
        reasoning_port=ReasoningFake(RuntimeError("C:\\private token=abc"))
    ).firmware_agent_port()

    with pytest.raises(FirmwareGenerationRejected) as error:
        asyncio.run(agent.generate(_request()))

    assert str(error.value) == "firmware generation was rejected"
