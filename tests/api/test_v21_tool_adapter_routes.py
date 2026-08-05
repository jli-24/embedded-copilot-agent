from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.hardware_observation.contracts import (
    BootStatus,
    HealthStatus,
    ObservationSnapshot,
)
from embedded_copilot.services.config import Settings
from embedded_copilot.tool_adapter.contracts import (
    ToolCapabilitySnapshot,
    ToolCapabilityStatus,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolType,
)


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _Port:
    def __init__(self):
        self.calls = 0

    def get_snapshot(self, project_id):
        self.calls += 1
        return ToolCapabilitySnapshot.create(
            tool_name="ESP-IDF",
            version="5.2",
            capabilities=("build",),
            status=ToolCapabilityStatus.AVAILABLE,
        )

    def build(self, request):
        self.calls += 1
        return ToolExecutionResult.create(
            status=ToolExecutionStatus.SUCCESS,
            tool_type=ToolType.ESP_IDF,
            operation="build",
            artifact_reference=request.artifact_reference,
            summary="Build projection",
        )

    def get_device(self, project_id):
        self.calls += 1
        return ObservationSnapshot.create(
            device_id="device-1",
            boot_status=BootStatus.BOOTED,
            firmware_version="PROJECTED",
            health_status=HealthStatus.HEALTHY,
            error_summary="",
        )


def test_status_build_and_device_use_injected_ports_once() -> None:
    port = _Port()
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        tool_adapter_status_port=port,
        tool_adapter_build_port=port,
        tool_adapter_device_port=port,
    )
    with TestClient(app) as client:
        assert client.get("/api/toolchain/v21/status/demo").status_code == 200
        assert client.post(
            "/api/toolchain/v21/build",
            json={"artifact_reference": "a1", "workspace_reference": "w1"},
        ).json() == {"error": "BUILD_APPROVAL_REQUIRED"}
        assert (
            client.post(
                "/api/toolchain/v21/build",
                json={
                    "artifact_reference": "a1",
                    "workspace_reference": "w1",
                    "approval_reference": "ap1",
                },
            ).status_code
            == 200
        )
        assert client.get("/api/toolchain/v21/device/demo").status_code == 200
    assert port.calls == 3


def test_missing_ports_are_safe() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/toolchain/v21/status/demo").json() == {
            "error": "TOOL_UNAVAILABLE"
        }
        assert client.post(
            "/api/toolchain/v21/flash",
            json={"firmware_reference": "f1", "device_reference": "d1"},
        ).json() == {"error": "FLASH_APPROVAL_REQUIRED"}
        assert client.get("/api/toolchain/v21/device/demo").json() == {
            "error": "OBSERVATION_UNAVAILABLE"
        }
