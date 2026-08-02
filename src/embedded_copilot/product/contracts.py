"""Public stateless Product Workspace contract."""

from __future__ import annotations

from typing import Protocol

from embedded_copilot.product.integration.core import CreateProjectRequest
from embedded_copilot.product.models import (
    EngineeringDashboardProjection,
    EngineeringReleaseReport,
    EngineeringWorkspace,
    ProjectSession,
)


class ProductWorkspacePort(Protocol):
    def create_project(self, request: CreateProjectRequest) -> EngineeringWorkspace: ...

    def get_project(self, workspace: EngineeringWorkspace) -> ProjectSession: ...

    def get_progress(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringDashboardProjection: ...

    def generate_report(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringReleaseReport: ...


__all__ = ("ProductWorkspacePort",)
