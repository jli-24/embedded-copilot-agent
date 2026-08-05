from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.firmware_engineering.adapters.fake import (
    FakeFirmwareBuildPort,
    FakeFirmwareParserPort,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


class _DebugPort:
    def get_snapshot(self, project_id):
        return None


def test_firmware_routes_success_and_build_approval() -> None:
    build = FakeFirmwareBuildPort()
    app = create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        firmware_engineering_port=FakeFirmwareParserPort(),
        firmware_build_port=build,
        firmware_debug_port=_DebugPort(),
    )
    with TestClient(app) as client:
        project = client.get("/api/firmware/v24/demo")
        missing = client.post(
            "/api/firmware/v24/build",
            json={
                "project_id": "demo",
                "firmware_reference": "firmware:demo",
                "build_profile": "debug",
            },
        )
        success = client.post(
            "/api/firmware/v24/build",
            json={
                "project_id": "demo",
                "firmware_reference": "firmware:demo",
                "build_profile": "debug",
                "approval_reference": "approval:1",
            },
        )
    assert project.status_code == 200
    assert project.json()["project_id"] == "demo"
    assert missing.json() == {"error": "BUILD_APPROVAL_REQUIRED"}
    assert success.status_code == 200
    assert success.json()["status"] == "SUCCESS"


def test_firmware_routes_are_unavailable_without_ports() -> None:
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/firmware/v24/demo").json() == {
            "error": "FIRMWARE_UNAVAILABLE"
        }
        assert client.get("/api/firmware/v24/build/demo").json() == {
            "error": "BUILD_UNAVAILABLE"
        }
        assert client.get("/api/firmware/v24/debug/demo").json() == {
            "error": "FIRMWARE_UNAVAILABLE"
        }
