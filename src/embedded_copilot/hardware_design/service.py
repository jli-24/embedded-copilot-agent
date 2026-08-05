from __future__ import annotations

import copy

from .contracts import (
    HardwareDesignPort,
    UnifiedHardwareModel,
    validate_unified_hardware_model,
)
from .exceptions import DesignRejected
from .models import _v22_id


class HardwareDesignService:
    __slots__ = ("_port",)

    def __init__(self, port: HardwareDesignPort) -> None:
        if not isinstance(port, HardwareDesignPort):
            raise TypeError("hardware design port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> UnifiedHardwareModel | None:
        try:
            project = _v22_id(project_id, field="project_id")
            result = self._port.get_snapshot(copy.deepcopy(project))
            if result is None:
                return None
            checked = validate_unified_hardware_model(result)
            if checked.project_id != project:
                raise ValueError("project binding mismatch")
            return checked
        except DesignRejected:
            raise
        except Exception as error:
            raise DesignRejected() from error
