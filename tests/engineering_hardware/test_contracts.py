from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_hardware import (
    HardwareEngineeringRequest,
)

from .conftest import NOW


def test_request_is_frozen_strict_and_tuple_safe(intelligence_snapshot) -> None:
    request = HardwareEngineeringRequest(
        proposal_id="proposal-1",
        requirement=intelligence_snapshot.requirement,
        plan=intelligence_snapshot.plan,
        context=intelligence_snapshot.context,
        proposed_at=NOW,
    )

    with pytest.raises(ValidationError):
        request.proposal_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        HardwareEngineeringRequest(
            proposal_id="proposal-1",
            requirement=intelligence_snapshot.requirement,
            plan=intelligence_snapshot.plan,
            context=intelligence_snapshot.context,
            proposed_at=NOW,
            content="private",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        HardwareEngineeringRequest(
            proposal_id="proposal-1",
            requirement=intelligence_snapshot.requirement,
            plan=intelligence_snapshot.plan,
            context=intelligence_snapshot.context,
            proposed_at=datetime(2026, 8, 4, 9, 0),
        )


def test_request_preserves_typed_intelligence_contracts(
    intelligence_snapshot,
) -> None:
    request = HardwareEngineeringRequest(
        proposal_id="proposal-1",
        requirement=intelligence_snapshot.requirement,
        plan=intelligence_snapshot.plan,
        context=intelligence_snapshot.context,
        proposed_at=NOW,
    )

    assert type(request.requirement) is type(intelligence_snapshot.requirement)
    assert type(request.plan) is type(intelligence_snapshot.plan)
    assert type(request.context) is type(intelligence_snapshot.context)
