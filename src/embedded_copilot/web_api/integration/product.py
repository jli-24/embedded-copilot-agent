"""Exact typed adapter for the public Product Layer."""

from __future__ import annotations

from embedded_copilot.product import (
    CreateProjectRequest,
    EngineeringDashboardProjection,
    EngineeringReleaseReport,
    EngineeringTimelineProjection,
    EngineeringWorkspace,
    ProductWorkspacePort,
    ProjectSession,
)
from embedded_copilot.web_api.exceptions import WebDependencyUnavailable


class ProductGateway:
    __slots__ = ("_port",)

    def __init__(self, port: object) -> None:
        if not all(
            callable(getattr(port, name, None))
            for name in (
                "create_project",
                "get_project",
                "get_progress",
                "generate_report",
            )
        ):
            raise TypeError("product_port is invalid")
        self._port: ProductWorkspacePort = port  # type: ignore[assignment]

    def create(self, request: object) -> EngineeringWorkspace:
        checked = _copy(request, CreateProjectRequest)
        return _copy_result(self._port.create_project(checked), EngineeringWorkspace)

    def workspace(self, value: object) -> EngineeringWorkspace:
        return _copy(value, EngineeringWorkspace)

    def project(self, workspace: EngineeringWorkspace) -> ProjectSession:
        return _copy_result(self._port.get_project(workspace), ProjectSession)

    def dashboard(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringDashboardProjection:
        return _copy_result(
            self._port.get_progress(workspace), EngineeringDashboardProjection
        )

    def timeline(
        self, workspace: EngineeringWorkspace
    ) -> EngineeringTimelineProjection:
        return _copy(workspace.timeline, EngineeringTimelineProjection)

    def report(self, workspace: EngineeringWorkspace) -> EngineeringReleaseReport:
        return _copy_result(
            self._port.generate_report(workspace), EngineeringReleaseReport
        )


def _copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise WebDependencyUnavailable("web dependency is unavailable") from None
    try:
        return expected_type.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError):
        raise WebDependencyUnavailable("web dependency is unavailable") from None


def _copy_result(value: object, expected_type: type):
    return _copy(value, expected_type)
