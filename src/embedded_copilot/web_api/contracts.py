"""Injected Web Console composition contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.web_api.models import (
    WebAttachmentProjection,
    WebAttachmentProjectionRequest,
    WebProjectCreateRequest,
)


@runtime_checkable
class WebProjectPreparationPort(Protocol):
    def prepare(self, request: WebProjectCreateRequest) -> object: ...


@runtime_checkable
class WebProjectRepositoryPort(Protocol):
    def save(self, workspace: object) -> None: ...

    def load(self, project_id: str) -> object: ...


@runtime_checkable
class WebAttachmentProjectionPort(Protocol):
    def project(
        self, request: WebAttachmentProjectionRequest
    ) -> WebAttachmentProjection: ...
