from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import PurePath
from threading import RLock
from typing import Protocol

from pydantic import Field, field_validator

from embedded_copilot.intelligence._validation import safe_identifier, safe_text
from embedded_copilot.intelligence.models import IntelligenceContractModel
from embedded_copilot.multimodal.models import MultimodalInput


class AttachmentBindingNotFound(LookupError):
    """The session-bound attachment reference does not exist."""


class AttachmentBindingConflict(RuntimeError):
    """The attachment reference conflicts with existing session metadata."""


class AttachmentBinding(IntelligenceContractModel):
    session_id: str
    input: MultimodalInput
    basename: str
    size_bytes: int = Field(ge=0)
    created_at: datetime

    @field_validator("session_id", mode="before")
    @classmethod
    def validate_session_id(cls, value: object) -> str:
        return safe_identifier(value, field="session_id")

    @field_validator("basename", mode="before")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("basename must be a string")
        candidate = value.strip()
        if (
            not candidate
            or PurePath(candidate).name != candidate
            or "/" in candidate
            or "\\" in candidate
            or candidate in {".", ".."}
        ):
            raise ValueError("basename must not contain a path")
        return safe_text(candidate, field="basename", max_length=255)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("created_at must use UTC")
        return value


class AttachmentBindingRepository(Protocol):
    def bind(self, binding: AttachmentBinding) -> None: ...

    def get(self, session_id: str, reference_id: str) -> AttachmentBinding: ...

    def list(self, session_id: str) -> tuple[AttachmentBinding, ...]: ...


class ProcessLocalAttachmentBindingRepository:
    """Bounded process-local metadata repository; it never stores file content."""

    def __init__(
        self,
        *,
        max_sessions: int = 100,
        max_references_per_session: int = 32,
    ) -> None:
        if max_sessions < 1 or max_references_per_session < 1:
            raise ValueError("attachment repository bounds are invalid")
        self._max_sessions = max_sessions
        self._max_references_per_session = max_references_per_session
        self._bindings: dict[str, dict[str, AttachmentBinding]] = {}
        self._lock = RLock()

    def bind(self, binding: AttachmentBinding) -> None:
        snapshot = self._snapshot(binding)
        session_key = snapshot.session_id.casefold()
        reference_key = snapshot.input.reference_id.casefold()
        with self._lock:
            session = self._bindings.get(session_key)
            if session is None:
                if len(self._bindings) >= self._max_sessions:
                    raise AttachmentBindingConflict(
                        "attachment repository capacity reached"
                    )
                session = {}
                self._bindings[session_key] = session
            if reference_key in session:
                raise AttachmentBindingConflict("attachment reference already exists")
            if len(session) >= self._max_references_per_session:
                raise AttachmentBindingConflict(
                    "attachment session capacity reached"
                )
            session[reference_key] = snapshot

    def get(self, session_id: str, reference_id: str) -> AttachmentBinding:
        session_key = safe_identifier(session_id, field="session_id").casefold()
        reference_key = safe_identifier(
            reference_id,
            field="reference_id",
        ).casefold()
        with self._lock:
            try:
                binding = self._bindings[session_key][reference_key]
            except KeyError:
                raise AttachmentBindingNotFound(
                    "attachment reference was not found"
                ) from None
            return self._snapshot(binding)

    def list(self, session_id: str) -> tuple[AttachmentBinding, ...]:
        session_key = safe_identifier(session_id, field="session_id").casefold()
        with self._lock:
            session = self._bindings.get(session_key, {})
            return tuple(self._snapshot(item) for item in session.values())

    @staticmethod
    def _snapshot(binding: AttachmentBinding) -> AttachmentBinding:
        if not isinstance(binding, AttachmentBinding):
            raise TypeError("attachment binding is invalid")
        return AttachmentBinding.model_validate(
            copy.deepcopy(binding.model_dump(mode="python"))
        )
