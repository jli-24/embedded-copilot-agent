from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.hil_validation.adapters.fake import (
    FakeDeviceObservationPort,
    FakeHILValidationPort,
    FakeHardwareCapabilityPort,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def test_hil_routes_success_and_approval_boundary() -> None:
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        hil_validation_port=FakeHILValidationPort(),
        device_observation_port=FakeDeviceObservationPort(),
        hardware_capability_port=FakeHardwareCapabilityPort(),
    )
    with TestClient(app) as client:
        device = client.get("/api/hil/v25/device/demo")
        observation = client.get("/api/hil/v25/observation/demo")
        missing = client.post(
            "/api/hil/v25/validate",
            json={
                "project_id": "demo",
                "device_reference": "device:demo",
                "firmware_reference": "firmware:demo",
            },
        )
        result = client.post(
            "/api/hil/v25/validate",
            json={
                "project_id": "demo",
                "device_reference": "device:demo",
                "firmware_reference": "firmware:demo",
                "approval_reference": "approval:demo",
            },
        )
        latest = client.get("/api/hil/v25/result/demo")
    assert device.status_code == 200
    assert device.json()["board_type"] == "ESP32-S3"
    assert observation.status_code == 200
    assert missing.json() == {"error": "HIL_APPROVAL_REQUIRED"}
    assert result.status_code == 200
    assert result.json()["overall_status"] == "PASSED"
    assert latest.status_code == 200


def test_hil_routes_are_unavailable_without_ports() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/hil/v25/device/demo").json() == {
            "error": "DEVICE_UNAVAILABLE"
        }
        assert client.get("/api/hil/v25/observation/demo").json() == {
            "error": "OBSERVATION_UNAVAILABLE"
        }
        assert client.get("/api/hil/v25/result/demo").json() == {
            "error": "HIL_FAILED"
        }
