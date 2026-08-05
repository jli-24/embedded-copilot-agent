from __future__ import annotations

import copy

from .contracts import DigitalTwinPort, DigitalTwinSnapshot, validate_snapshot
from .exceptions import DigitalTwinRejected
from .models import identifier


class DigitalTwinService:
    __slots__ = ("_port",)

    def __init__(self, port: DigitalTwinPort) -> None:
        if not isinstance(port, DigitalTwinPort):
            raise TypeError("digital twin port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> DigitalTwinSnapshot | None:
        try:
            project = identifier(project_id, field="project_id")
            value = self._port.get_snapshot(copy.deepcopy(project))
            if value is None:
                return None
            checked = validate_snapshot(value)
            if checked.project_id != project:
                raise ValueError("project binding mismatch")
            return checked
        except Exception as error:
            raise DigitalTwinRejected() from error


__all__ = ["DigitalTwinService"]
