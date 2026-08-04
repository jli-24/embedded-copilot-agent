from __future__ import annotations

import copy

from .contracts import (
    ValidationSnapshot,
    ValidationSnapshotPort,
    validate_validation_snapshot,
)
from .exceptions import ValidationRejected
from .models import identifier


class ValidationLoopService:
    __slots__ = ("_port",)

    def __init__(self, port: ValidationSnapshotPort) -> None:
        if not isinstance(port, ValidationSnapshotPort):
            raise TypeError("validation port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> ValidationSnapshot | None:
        try:
            project = identifier(project_id, field="project_id")
            result = self._port.get_snapshot(copy.deepcopy(project))
            return None if result is None else validate_validation_snapshot(result)
        except ValidationRejected:
            raise
        except Exception as error:
            raise ValidationRejected() from error
