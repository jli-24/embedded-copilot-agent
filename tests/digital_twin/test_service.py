from __future__ import annotations

from embedded_copilot.digital_twin.adapters.fake import FakeDigitalTwinAdapter
from embedded_copilot.digital_twin.service import DigitalTwinService


def test_service_revalidates_and_binds_project_identity() -> None:
    result = DigitalTwinService(FakeDigitalTwinAdapter()).get_snapshot("demo")
    assert result.project_id == "demo"
    assert result.metrics.fingerprint.startswith("sha256:")
    assert result.constraints[0].reference.startswith("constraint:")

