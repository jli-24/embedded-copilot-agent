from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.device_runtime.contracts import (
    ConnectionStatus,
    DeviceSnapshot,
    DeviceType,
)
from embedded_copilot.hardware_observation.contracts import (
    BootStatus,
    HealthStatus,
    ObservationSnapshot,
)
from embedded_copilot.services.config import Settings
from embedded_copilot.toolchain.adapters.flash import FakeFlashAdapter
from embedded_copilot.validation_loop.contracts import (
    FlashState,
    LoopState,
    ObservationState,
    ValidationSnapshot,
    VerificationState,
)


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _Port:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def get_snapshot(self, project_id: str):
        self.calls += 1
        return self.value


def _client(**kwargs) -> TestClient:
    return TestClient(
        create_app(service=_ChatService(), settings=Settings(_env_file=None), **kwargs)
    )


def test_v19_routes_are_unavailable_without_ports() -> None:
    with _client() as client:
        assert client.get("/api/device/demo").json() == {"error": "DEVICE_UNAVAILABLE"}
        assert client.get("/api/validation/observation/demo").json() == {
            "error": "OBSERVATION_UNAVAILABLE"
        }
        assert client.get("/api/validation/loop/demo").json() == {
            "error": "VALIDATION_UNAVAILABLE"
        }
        assert client.post(
            "/api/validation/flash",
            json={"firmware_reference": "a", "device_reference": "b"},
        ).json() == {"error": "FLASH_UNAVAILABLE"}


def test_v19_snapshot_routes_validate_and_call_once() -> None:
    device = _Port(
        DeviceSnapshot.create(
            project_id="demo",
            device_id="board-1",
            device_type=DeviceType.ESP32,
            connection_status=ConnectionStatus.CONNECTED,
        )
    )
    observation = _Port(
        ObservationSnapshot.create(
            device_id="board-1",
            boot_status=BootStatus.BOOTED,
            firmware_version="1.0",
            health_status=HealthStatus.HEALTHY,
            error_summary="",
        )
    )
    validation = _Port(
        ValidationSnapshot.create(
            project_id="demo",
            firmware_reference="artifact-1",
            device_reference="board-1",
            build_status=LoopState.BUILD_READY,
            flash_status=FlashState.PENDING,
            observation_status=ObservationState.PENDING,
            verification_status=VerificationState.REVIEW_REQUIRED,
        )
    )
    with _client(
        device_snapshot_port=device,
        observation_snapshot_port=observation,
        validation_loop_port=validation,
        flash_port=FakeFlashAdapter(),
    ) as client:
        assert client.get("/api/device/demo").status_code == 200
        assert client.get("/api/validation/observation/demo").status_code == 200
        assert client.get("/api/validation/loop/demo").status_code == 200
        assert (
            client.post(
                "/api/validation/flash",
                json={
                    "firmware_reference": "artifact-1",
                    "device_reference": "board-1",
                    "approval_reference": "approval-1",
                    "capability_reference": "capability-1",
                },
            ).status_code
            == 200
        )
    assert device.calls == observation.calls == validation.calls == 1


def test_flash_capability_and_invalid_snapshots_are_safe() -> None:
    device = _Port(
        {
            "project_id": "demo",
            "device_id": "board-1",
            "device_type": "ESP32",
            "connection_status": "CONNECTED",
            "fingerprint": "sha256:" + "0" * 64,
        }
    )
    with _client(device_snapshot_port=device, flash_port=FakeFlashAdapter()) as client:
        response = client.post(
            "/api/validation/flash",
            json={
                "firmware_reference": "artifact-1",
                "device_reference": "board-1",
                "approval_reference": "approval-1",
            },
        )
        assert response.status_code == 422
        assert response.json() == {"error": "FLASH_CAPABILITY_REQUIRED"}
        assert client.get("/api/device/demo").json() == {
            "error": "DEVICE_SNAPSHOT_REJECTED"
        }
        assert "0" * 64 not in response.text
