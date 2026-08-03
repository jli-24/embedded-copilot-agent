import asyncio

from embedded_copilot.datasheet_agent import project_datasheet_evidence
from embedded_copilot.datasheet_runtime.contracts.models import (
    DatasheetRequest,
    DatasheetResponse,
    DatasheetSummary,
    InterfaceCandidate,
)


class _Port:
    async def analyze(self, request: DatasheetRequest) -> DatasheetResponse:
        return DatasheetResponse(
            summary=DatasheetSummary(
                file_id=request.file_id,
                interface_candidates=(InterfaceCandidate(name="SPI"),),
            )
        )


def test_datasheet_adapter_projects_only_existing_candidates() -> None:
    values = asyncio.run(
        project_datasheet_evidence(
            _Port(),
            session_id="session-1",
            file_id="datasheet-1",
            reference_id="datasheet-1",
        )
    )
    assert len(values) == 1
    assert values[0].trust_basis.value == "PROJECTED"
    assert values[0].confidence == 0.5
    assert "GPIO" not in values[0].summary
