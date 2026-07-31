from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from embedded_copilot.datasheet_runtime import (
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
)
from embedded_copilot.datasheet_runtime.contracts.models import (
    ComponentCandidate,
    InterfaceCandidate,
)
from embedded_copilot.knowledge.intelligence import (
    DatasheetKnowledgeRequest,
    EngineeringKnowledgeRequest,
    KnowledgeIntelligencePort,
    KnowledgeObservationTimeout,
    KnowledgeSourceCandidate,
    KnowledgeSourceType,
    SourceTrustCatalog,
    create_knowledge_intelligence_runtime,
)

from .conftest import source_candidate


class RecordingWebSource:
    source_type = KnowledgeSourceType.WEB

    def __init__(self, candidates: tuple[KnowledgeSourceCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls = 0

    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> tuple[KnowledgeSourceCandidate, ...]:
        self.calls += 1
        assert request.request_id == "knowledge-request-1"
        return self.candidates


class TimeoutWebSource:
    def retrieve(
        self,
        request: EngineeringKnowledgeRequest,
    ) -> tuple[KnowledgeSourceCandidate, ...]:
        raise TimeoutError from None


class RecordingDatasheetPort:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        self.calls += 1
        return DatasheetResponse(
            summary=DatasheetSummary(
                file_id=request.file_id,
                component_candidate=ComponentCandidate(
                    family="ESP32", model="ESP32-S3"
                ),
                interface_candidates=(InterfaceCandidate(name="SPI"),),
            )
        )


def test_runtime_calls_injected_source_once_and_returns_verified_evidence(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    source = RecordingWebSource(
        (
            source_candidate(
                evidence_id="community-1",
                publisher="Community A",
                observed_at=observed_at,
            ),
            source_candidate(
                evidence_id="community-2",
                publisher="Community B",
                observed_at=observed_at,
            ),
        )
    )
    runtime = create_knowledge_intelligence_runtime(
        trust_catalog=trust_catalog,
        web_source=source,
    )

    result = runtime.knowledge_port().retrieve(
        EngineeringKnowledgeRequest(
            request_id="knowledge-request-1",
            query_summary="ESP32-S3 camera interface",
        )
    )

    assert isinstance(runtime.knowledge_port(), KnowledgeIntelligencePort)
    assert source.calls == 1
    assert len(result.verified_evidence) == 1
    assert result.trace[-1].stage == "verification"
    for name in (
        "provider",
        "registry",
        "graph",
        "settings",
        "configuration",
        "datasheet_port",
    ):
        assert not hasattr(runtime, name)


def test_runtime_maps_source_timeout_without_leaking_details(
    trust_catalog: SourceTrustCatalog,
) -> None:
    runtime = create_knowledge_intelligence_runtime(
        trust_catalog=trust_catalog,
        web_source=TimeoutWebSource(),
    )
    request = EngineeringKnowledgeRequest(
        request_id="knowledge-request-1",
        query_summary="ESP32-S3 camera interface",
    )

    with pytest.raises(KnowledgeObservationTimeout) as error:
        runtime.knowledge_port().retrieve(request)

    assert str(error.value) == "knowledge observation timed out"


def test_datasheet_delegates_typed_request_without_file_or_byte_access(
    trust_catalog: SourceTrustCatalog,
    observed_at: datetime,
) -> None:
    datasheet = RecordingDatasheetPort()
    runtime = create_knowledge_intelligence_runtime(
        trust_catalog=trust_catalog,
        datasheet_port=datasheet,
    )
    request = DatasheetKnowledgeRequest(
        request_id="datasheet-knowledge-1",
        datasheet_request=DatasheetRequest(
            session_id="session-1",
            file_id="file-1",
            instruction_summary="Analyze safe datasheet structure.",
        ),
        publisher="Espressif",
        reference="datasheet:esp32-s3:section-5.2",
        observed_at=observed_at,
    )

    result = asyncio.run(runtime.knowledge_port().analyze_datasheet(request))

    assert datasheet.calls == 1
    assert tuple(item.entity_type.value for item in result.verified_evidence) == (
        "COMPONENT",
        "INTERFACE",
    )
    serialized = result.model_dump_json()
    assert "bytes" not in serialized
    assert "path" not in serialized
