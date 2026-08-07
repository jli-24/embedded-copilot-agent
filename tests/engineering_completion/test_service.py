from __future__ import annotations

from embedded_copilot.engineering_completion.adapters.fake import (
    FakeEngineeringCompletionPort,
)
from embedded_copilot.engineering_completion.contracts import (
    ValidationReason,
    ValidationStatus,
)
from embedded_copilot.engineering_completion.service import EngineeringCompletionService


def test_service_revalidates_and_binds_project() -> None:
    service = EngineeringCompletionService(FakeEngineeringCompletionPort())
    snapshot = service.get_snapshot("demo")
    assert snapshot is not None
    assert snapshot.project_id == "demo"
    result = service.validate("demo", snapshot, snapshot.fingerprint)
    assert result.status is ValidationStatus.VALID
    assert result.reason is None


def test_service_reports_internal_reason_without_public_leak() -> None:
    service = EngineeringCompletionService(FakeEngineeringCompletionPort())
    snapshot = service.get_snapshot("demo")
    assert snapshot is not None
    result = service.validate("other", snapshot, snapshot.fingerprint)
    assert result.status is ValidationStatus.REJECTED
    assert result.reason is ValidationReason.PROJECT_MISMATCH
    assert "reason" not in result.model_dump()
