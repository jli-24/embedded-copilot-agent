"""Injected Web Console composition contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_observation import BuildObservationProjection
from embedded_copilot.execution import BuildApproval, BuildResult
from embedded_copilot.firmware_agent import FirmwareProposal
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


@runtime_checkable
class WebFirmwareProposalRepositoryPort(Protocol):
    def save(self, key: str, value: FirmwareProposal) -> None: ...

    def load(self, key: str) -> FirmwareProposal: ...


@runtime_checkable
class WebBuildResultRepositoryPort(Protocol):
    def save(self, key: str, value: object) -> None: ...

    def load(self, key: str) -> object: ...


@runtime_checkable
class WebObservationProjectionPort(Protocol):
    def observe(self, result: BuildResult) -> BuildObservationProjection: ...


@runtime_checkable
class WebBuildApprovalPort(Protocol):
    def resolve(
        self,
        *,
        approval_reference_id: str,
        build_id: str,
        proposal_fingerprint: str,
    ) -> BuildApproval: ...
