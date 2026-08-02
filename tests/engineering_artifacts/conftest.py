from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.engineering_artifacts import EngineeringGenerationRequest
from embedded_copilot.engineering_validation import (
    create_hardware_validation_runtime,
)
from tests.engineering_validation import conftest as _validation_fixtures

firmware_request = _validation_fixtures.firmware_request
validation_setup = _validation_fixtures.validation_setup

NOW = datetime(2026, 8, 7, 9, 0, tzinfo=UTC)


@pytest.fixture
def generation_request(request: pytest.FixtureRequest) -> EngineeringGenerationRequest:
    validation_setup = request.getfixturevalue("validation_setup")
    validation_request, evidence_port = validation_setup
    validation = (
        create_hardware_validation_runtime(evidence_port=evidence_port)
        .hardware_validation_port()
        .validate(validation_request)
    )
    return EngineeringGenerationRequest(
        proposal_id="artifact-proposal-1",
        requirement=validation_request.requirement,
        context=validation_request.context,
        hardware_proposal=validation_request.hardware_proposal,
        firmware_proposal=validation_request.firmware_proposal,
        validation_report=validation,
        proposed_at=NOW,
    )
