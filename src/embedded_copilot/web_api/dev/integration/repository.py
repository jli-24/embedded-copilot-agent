"""Explicit Product repository integration used only by the demo."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.product import EngineeringWorkspace
from embedded_copilot.web_api import WebProjectNotFound


class InMemoryWebProjectRepository:
    """Store immutable workspace copies for one development process."""

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items: dict[str, EngineeringWorkspace] = {}

    def save(self, workspace: object) -> None:
        checked = _workspace(workspace)
        self._items[checked.project_id] = checked

    def load(self, project_id: str) -> EngineeringWorkspace:
        if type(project_id) is not str:
            raise WebProjectNotFound("project is unavailable") from None
        try:
            return _workspace(self._items[project_id])
        except KeyError:
            raise WebProjectNotFound("project is unavailable") from None


def _workspace(value: object) -> EngineeringWorkspace:
    if type(value) is not EngineeringWorkspace:
        raise TypeError("typed demo workspace is required")
    try:
        return EngineeringWorkspace.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise ValueError("demo workspace is invalid") from None
