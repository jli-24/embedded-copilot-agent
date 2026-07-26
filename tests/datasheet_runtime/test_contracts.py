from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

import embedded_copilot.datasheet_runtime as datasheet_runtime
from embedded_copilot.datasheet_runtime import (
    DatasheetIntelligencePort,
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
)


def _summary() -> DatasheetSummary:
    return DatasheetSummary(
        file_id="file:1",
        component_candidate={
            "semantics": "candidate",
            "family": "STM32",
            "model": "STM32F103C8T6",
        },
        interface_candidates=(
            {"semantics": "candidate", "name": "SPI"},
        ),
        electrical_candidates=(
            {
                "semantics": "candidate",
                "kind": "voltage_range",
                "minimum": 2.0,
                "maximum": 3.6,
                "unit": "V",
            },
        ),
        section_candidates=(
            {
                "semantics": "candidate",
                "name": "Electrical Characteristics",
            },
        ),
    )


def test_datasheet_contracts_are_frozen_strict_candidates() -> None:
    request = DatasheetRequest(
        session_id="session:1",
        file_id="file:1",
        instruction_summary="Extract unverified datasheet candidates.",
    )
    response = DatasheetResponse(summary=_summary())

    assert tuple(DatasheetRequest.model_fields) == (
        "session_id",
        "file_id",
        "instruction_summary",
    )
    assert tuple(DatasheetSummary.model_fields) == (
        "candidate_semantics",
        "file_id",
        "component_candidate",
        "interface_candidates",
        "electrical_candidates",
        "section_candidates",
    )
    assert request.model_config["frozen"] is True
    assert request.model_config["extra"] == "forbid"
    assert response.output_type == "reasoning_suggestion"
    assert response.review_required is True
    assert response.summary.candidate_semantics == "unverified"
    assert response.summary.component_candidate is not None
    assert response.summary.component_candidate.semantics == "candidate"
    assert all(
        item.semantics == "candidate"
        for item in (
            *response.summary.interface_candidates,
            *response.summary.electrical_candidates,
            *response.summary.section_candidates,
        )
    )

    with pytest.raises(ValidationError):
        request.file_id = "file:2"
    with pytest.raises(ValidationError):
        DatasheetRequest(
            session_id="session:1",
            file_id="file:1",
            instruction_summary="Inspect candidates.",
            path=r"C:\private\datasheet.pdf",
        )


@pytest.mark.parametrize(
    "field",
    (
        "filename",
        "path",
        "absolute_path",
        "bytes",
        "binary",
        "content",
        "base64",
        "file_url",
        "model",
        "provider",
        "endpoint",
        "credential",
    ),
)
def test_datasheet_request_rejects_infrastructure_fields(field: str) -> None:
    payload: dict[str, object] = {
        "session_id": "session:1",
        "file_id": "file:1",
        "instruction_summary": "Extract candidates.",
        field: "private-value",
    }

    with pytest.raises(ValidationError):
        DatasheetRequest.model_validate(payload)


def test_candidate_models_reject_fact_semantics_and_invalid_ranges() -> None:
    payload = _summary().model_dump(mode="json")
    payload["component_candidate"]["semantics"] = "engineering_fact"
    with pytest.raises(ValidationError):
        DatasheetSummary.model_validate(payload)

    payload = _summary().model_dump(mode="json")
    payload["electrical_candidates"][0]["minimum"] = 4.0
    payload["electrical_candidates"][0]["maximum"] = 3.0
    with pytest.raises(ValidationError):
        DatasheetSummary.model_validate(payload)

    payload = _summary().model_dump(mode="json")
    payload["electrical_candidates"][0]["minimum"] = None
    payload["electrical_candidates"][0]["maximum"] = None
    with pytest.raises(ValidationError):
        DatasheetSummary.model_validate(payload)


def test_public_boundary_exports_only_safe_runtime_contracts() -> None:
    assert datasheet_runtime.__all__ == [
        "DatasheetAnalysisTimeout",
        "DatasheetDocumentRejected",
        "DatasheetIntelligencePort",
        "DatasheetRequest",
        "DatasheetResponse",
        "DatasheetRuntime",
        "DatasheetRuntimeError",
        "DatasheetRuntimeUnavailable",
        "DatasheetSummary",
        "create_datasheet_runtime",
    ]
    assert tuple(
        inspect.signature(DatasheetIntelligencePort.analyze).parameters
    ) == ("self", "request")
    for forbidden in (
        "ComponentCandidate",
        "InterfaceCandidate",
        "ElectricalCandidate",
        "SectionCandidate",
        "EngineeringFact",
        "Evidence",
        "Decision",
        "Artifact",
        "FileWritePort",
    ):
        assert not hasattr(datasheet_runtime, forbidden)
