from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.component_recommendation import ComponentRecommendation
from embedded_copilot.services.config import Settings
from embedded_copilot.toolchain.contracts import (
    BuildStatus,
    ToolchainArtifactReference,
    ToolchainSnapshot,
    WorkspaceStatus,
)
from embedded_copilot.workspace_projection.contracts import (
    ProjectionStatus,
    WorkspaceArtifactView,
    WorkspaceSnapshot,
    WorkspaceSnapshotStatus,
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


class _Components:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def get_recommendations(self, project_id: str):
        self.calls += 1
        return self.value


def _client(**kwargs) -> TestClient:
    return TestClient(
        create_app(service=_ChatService(), settings=Settings(_env_file=None), **kwargs)
    )


def test_snapshot_routes_are_unavailable_without_ports() -> None:
    with _client() as client:
        assert client.get("/api/workspace/demo").json() == {
            "error": "WORKSPACE_UNAVAILABLE"
        }
        assert client.get("/api/toolchain/demo").json() == {
            "error": "TOOLCHAIN_UNAVAILABLE"
        }
        assert client.get("/api/components/demo").json() == {
            "error": "COMPONENT_UNAVAILABLE"
        }


def test_snapshot_routes_validate_and_call_once() -> None:
    workspace = _Port(
        WorkspaceSnapshot.create(
            project_id="demo",
            artifacts=(
                WorkspaceArtifactView(
                    artifact_id="artifact-1",
                    artifact_type="FIRMWARE",
                    status=ProjectionStatus.WAITING_APPROVAL,
                    filenames=("main.c",),
                ),
            ),
            status=WorkspaceSnapshotStatus.WAITING_APPROVAL,
        )
    )
    toolchain = _Port(
        ToolchainSnapshot.create(
            build_status=BuildStatus.SUCCESS,
            artifact=ToolchainArtifactReference(
                reference_id="artifact-1", artifact_type="FIRMWARE"
            ),
            workspace_status=WorkspaceStatus.APPROVED,
        )
    )
    components = _Components(
        (
            ComponentRecommendation(
                part_number="ESP32-S3",
                manufacturer="Espressif",
                reason="fit",
                datasheet_reference="datasheet:1",
                supplier_links=("https://supplier.example/esp32-s3",),
                alternatives=("STM32F4",),
            ),
        )
    )
    with _client(
        workspace_snapshot_port=workspace,
        toolchain_snapshot_port=toolchain,
        component_recommendation_port=components,
    ) as client:
        assert client.get("/api/workspace/demo").status_code == 200
        assert client.get("/api/toolchain/demo").status_code == 200
        assert client.get("/api/components/demo").status_code == 200
    assert workspace.calls == toolchain.calls == components.calls == 1


def test_invalid_results_are_sanitized() -> None:
    with _client(
        workspace_snapshot_port=_Port({"path": "private"}),
        toolchain_snapshot_port=_Port({"command": "idf.py"}),
        component_recommendation_port=_Components([{"provider": "secret"}]),
    ) as client:
        assert client.get("/api/workspace/demo").json() == {
            "error": "WORKSPACE_SNAPSHOT_REJECTED"
        }
        assert client.get("/api/toolchain/demo").json() == {
            "error": "TOOLCHAIN_SNAPSHOT_REJECTED"
        }
        assert client.get("/api/components/demo").json() == {
            "error": "COMPONENT_RECOMMENDATION_REJECTED"
        }
