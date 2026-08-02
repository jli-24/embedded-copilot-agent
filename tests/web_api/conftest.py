from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from embedded_copilot.product import (
    CreateProjectRequest,
    EngineeringWorkspace,
    create_product_runtime,
)
from embedded_copilot.web_api import (
    WebAttachmentProjection,
    WebAttachmentProjectionRequest,
    WebProjectCreateRequest,
    WebProjectNotFound,
    create_web_api_app,
    web_attachment_fingerprint,
)
from tests.product.conftest import artifact_report as artifact_report
from tests.product.conftest import feedback_sources as feedback_sources
from tests.product.conftest import firmware_request as firmware_request
from tests.product.conftest import generation_request as generation_request
from tests.product.conftest import make_request
from tests.product.conftest import product_sources as product_sources
from tests.product.conftest import validation_setup as validation_setup


@dataclass
class PreparationFake:
    sources: dict[str, object]
    calls: list[WebProjectCreateRequest] = field(default_factory=list)

    def prepare(self, request: WebProjectCreateRequest) -> CreateProjectRequest:
        self.calls.append(request.model_copy(deep=True))
        return make_request(
            self.sources,
            project_summary=request.requirement,
        )


@dataclass
class RepositoryFake:
    items: dict[str, EngineeringWorkspace] = field(default_factory=dict)
    saves: int = 0
    loads: int = 0

    def save(self, workspace: EngineeringWorkspace) -> None:
        self.saves += 1
        self.items[workspace.project_id] = workspace.model_copy(deep=True)

    def load(self, project_id: str) -> EngineeringWorkspace:
        self.loads += 1
        try:
            return self.items[project_id].model_copy(deep=True)
        except KeyError:
            raise WebProjectNotFound("not found") from None


@dataclass
class AttachmentFake:
    calls: list[WebAttachmentProjectionRequest] = field(default_factory=list)

    def project(
        self,
        request: WebAttachmentProjectionRequest,
    ) -> WebAttachmentProjection:
        self.calls.append(request.model_copy(deep=True))
        values = dict(
            project_id=request.project_id,
            session_id=request.session_id,
            reference_id=request.reference_id,
            attachment_type=request.attachment_type,
            basename=request.basename,
            summary=request.summary,
            size_bytes=request.size_bytes,
            observed_at=request.observed_at,
            source_fingerprint=request.fingerprint,
        )
        return WebAttachmentProjection(
            **values,
            fingerprint=web_attachment_fingerprint(**values),
        )


@pytest.fixture
def web_setup(product_sources):
    preparation = PreparationFake(product_sources)
    repository = RepositoryFake()
    attachment = AttachmentFake()
    product_port = create_product_runtime().product_workspace_port()
    app = create_web_api_app(
        product_port=product_port,
        preparation_port=preparation,
        repository_port=repository,
        attachment_port=attachment,
    )
    return TestClient(app), preparation, repository, attachment
