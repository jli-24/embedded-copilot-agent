from __future__ import annotations

from dataclasses import dataclass, field

from fastapi.testclient import TestClient

from embedded_copilot.engineering_observation import (
    create_engineering_observation_service,
)
from embedded_copilot.execution import (
    BuildApproval,
    BuildApprovalStatus,
    BuildExecutionRequest,
    BuildResult,
    BuildStatus,
    build_approval_fingerprint,
    build_result_fingerprint,
)
from embedded_copilot.firmware_agent import (
    FirmwareGenerationRequest,
    FirmwareProposal,
    firmware_proposal_fingerprint,
)
from embedded_copilot.product import create_product_runtime
from embedded_copilot.web_api import create_web_api_app
from tests.execution.test_build_execution import NOW, _proposal
from tests.web_api.conftest import AttachmentFake, PreparationFake, RepositoryFake


@dataclass
class FirmwarePortFake:
    proposal: FirmwareProposal
    calls: list[FirmwareGenerationRequest] = field(default_factory=list)

    async def generate(self, request: FirmwareGenerationRequest) -> FirmwareProposal:
        self.calls.append(request.model_copy(deep=True))
        values = {
            name: getattr(self.proposal, name)
            for name in type(self.proposal).model_fields
            if name != "fingerprint"
        }
        values["project_id"] = request.context.project_id
        values["source_context_fingerprint"] = request.context.fingerprint
        values["source_workspace_fingerprint"] = request.context.workspace_fingerprint
        return FirmwareProposal(
            **values,
            fingerprint=firmware_proposal_fingerprint(**values),
        )


@dataclass
class BuildPortFake:
    calls: list[BuildExecutionRequest] = field(default_factory=list)

    async def execute(self, request: BuildExecutionRequest) -> BuildResult:
        self.calls.append(request.model_copy(deep=True))
        values = {
            "build_id": request.build_id,
            "project_id": request.proposal.project_id,
            "proposal_fingerprint": request.proposal.fingerprint,
            "status": BuildStatus.SUCCESS,
            "diagnostic_codes": (),
            "symbol_references": (),
            "observed_at": request.requested_at,
        }
        return BuildResult(**values, fingerprint=build_result_fingerprint(**values))


@dataclass
class ApprovalPortFake:
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    def resolve(
        self,
        *,
        approval_reference_id: str,
        build_id: str,
        proposal_fingerprint: str,
    ) -> BuildApproval:
        self.calls.append((approval_reference_id, build_id, proposal_fingerprint))
        values = {
            "build_id": build_id,
            "proposal_fingerprint": proposal_fingerprint,
            "status": BuildApprovalStatus.APPROVED,
            "reviewer": "trusted-reviewer",
            "reviewed_at": NOW,
        }
        return BuildApproval(
            **values,
            fingerprint=build_approval_fingerprint(**values),
        )


@dataclass
class TypedRepository:
    items: dict[str, object] = field(default_factory=dict)

    def save(self, key: str, value: object) -> None:
        self.items[key] = value.model_copy(deep=True)

    def load(self, key: str) -> object:
        return self.items[key].model_copy(deep=True)


def test_firmware_generate_build_and_result_routes(product_sources) -> None:
    project_repository = RepositoryFake()
    firmware_repository = TypedRepository()
    build_repository = TypedRepository()
    firmware_port = FirmwarePortFake(_proposal())
    build_port = BuildPortFake()
    approval_port = ApprovalPortFake()
    app = create_web_api_app(
        product_port=create_product_runtime().product_workspace_port(),
        preparation_port=PreparationFake(product_sources),
        repository_port=project_repository,
        attachment_port=AttachmentFake(),
        firmware_agent_port=firmware_port,
        build_execution_port=build_port,
        build_approval_port=approval_port,
        observation_port=create_engineering_observation_service(),
        firmware_repository_port=firmware_repository,
        build_repository_port=build_repository,
    )
    client = TestClient(app)
    client.post("/api/projects", json={"requirement": "Camera"})

    generated = client.post(
        "/api/firmware/generate",
        json={
            "project_id": "project-1",
            "request_id": "firmware-1",
            "requested_at": NOW.isoformat(),
        },
    )
    assert generated.status_code == 200
    assert [item["logical_path"] for item in generated.json()["files"]] == [
        "CMakeLists.txt",
        "main/main.c",
    ]
    assert len(firmware_port.calls) == 1

    started = client.post(
        "/api/build/start",
        json={
            "build_id": "build-1",
            "firmware_request_id": "firmware-1",
            "approval_reference_id": "approval-1",
            "requested_at": NOW.isoformat(),
        },
    )
    assert started.status_code == 200
    assert started.json()["result"]["status"] == "SUCCESS"
    assert started.json()["observation"]["observation"]["observation_type"] == "BUILD_SUCCESS"
    assert len(build_port.calls) == 1
    assert len(approval_port.calls) == 1

    loaded = client.get("/api/build/result", params={"build_id": "build-1"})
    assert loaded.status_code == 200
    assert loaded.json() == started.json()
    serialized = loaded.text.lower()
    assert "environment" not in serialized
    assert "command" not in serialized
    assert "path" not in serialized


def test_v13_ports_are_optional_and_legacy_chat_remains_available(web_setup) -> None:
    client, _, _, _ = web_setup

    legacy = client.post("/api/chat", json={"message": "Create camera project"})
    unavailable = client.post(
        "/api/firmware/generate",
        json={
            "project_id": "project-1",
            "request_id": "firmware-1",
            "requested_at": NOW.isoformat(),
        },
    )

    assert legacy.status_code == 200
    assert legacy.json()["message"] == "Project Created"
    assert unavailable.status_code == 503
