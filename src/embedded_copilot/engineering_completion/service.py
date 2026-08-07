from __future__ import annotations

import copy

from .contracts import (
    EngineeringCompletionPort,
    EngineeringCompletionSnapshot,
    ValidationReason,
    ValidationResult,
    ValidationStatus,
    validate_completion_snapshot,
)
from .models import fingerprint, identifier, safe_text


class EngineeringCompletionService:
    __slots__ = ("_port",)

    def __init__(self, port: EngineeringCompletionPort) -> None:
        if not callable(getattr(port, "get_snapshot", None)):
            raise TypeError("engineering completion port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> EngineeringCompletionSnapshot | None:
        checked_project = identifier(project_id, field="project_id")
        value = self._port.get_snapshot(copy.deepcopy(checked_project))
        if value is None:
            return None
        checked = validate_completion_snapshot(value)
        if checked.project_id != checked_project:
            raise ValueError("project binding mismatch")
        return checked

    @staticmethod
    def validate(
        project_id: str,
        snapshot: EngineeringCompletionSnapshot,
        context_fingerprint: str,
    ) -> ValidationResult:
        checked_project = identifier(project_id, field="project_id")
        checked_context = fingerprint(context_fingerprint, field="context_fingerprint")
        try:
            checked_snapshot = validate_completion_snapshot(snapshot)
        except Exception as error:
            raise ValueError("completion snapshot rejected") from error
        if checked_snapshot.project_id != checked_project:
            return ValidationResult.create(
                project_id=checked_project,
                snapshot_fingerprint=checked_snapshot.fingerprint,
                context_fingerprint=checked_context,
                status=ValidationStatus.REJECTED,
                summary="Engineering completion projection was rejected.",
                reason=ValidationReason.PROJECT_MISMATCH,
            )
        if checked_context != checked_snapshot.fingerprint:
            return ValidationResult.create(
                project_id=checked_project,
                snapshot_fingerprint=checked_snapshot.fingerprint,
                context_fingerprint=checked_context,
                status=ValidationStatus.REJECTED,
                summary="Engineering completion context does not match the snapshot.",
                reason=ValidationReason.CONTEXT_MISMATCH,
            )
        return ValidationResult.create(
            project_id=checked_project,
            snapshot_fingerprint=checked_snapshot.fingerprint,
            context_fingerprint=checked_context,
            status=ValidationStatus.VALID,
            summary=safe_text(
                "Engineering completion projection is valid.", field="summary"
            ),
        )


__all__ = ["EngineeringCompletionService"]
