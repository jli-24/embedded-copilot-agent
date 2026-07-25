from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from threading import RLock
from typing import Protocol

from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.intelligence._validation import safe_identifier


class ConversationNotFound(LookupError):
    """The process-local conversation does not exist."""


class ConversationStateConflict(RuntimeError):
    """The process-local conversation cannot accept the state transition."""


class ConversationRepository(Protocol):
    def add(self, workspace: ProjectWorkspace) -> None: ...

    def get(self, session_id: str) -> ProjectWorkspace: ...

    def save(self, workspace: ProjectWorkspace) -> None: ...


class ProcessLocalConversationRepository:
    """Bounded in-memory snapshots; no restart recovery or disk persistence."""

    def __init__(
        self,
        *,
        max_sessions: int = 100,
        max_messages: int = 200,
    ) -> None:
        if max_sessions < 1 or max_messages < 1:
            raise ValueError("repository bounds are invalid")
        self._max_sessions = max_sessions
        self._max_messages = max_messages
        self._workspaces: dict[str, ProjectWorkspace] = {}
        self._lock = RLock()

    def add(self, workspace: ProjectWorkspace) -> None:
        snapshot = self._snapshot(workspace)
        key = snapshot.session.session_id.casefold()
        with self._lock:
            if key in self._workspaces:
                raise ConversationStateConflict("conversation already exists")
            if len(self._workspaces) >= self._max_sessions:
                raise ConversationStateConflict("repository capacity reached")
            self._check_message_bound(snapshot)
            self._workspaces[key] = snapshot

    def get(self, session_id: str) -> ProjectWorkspace:
        key = safe_identifier(session_id, field="session_id").casefold()
        with self._lock:
            try:
                workspace = self._workspaces[key]
            except KeyError:
                raise ConversationNotFound("conversation was not found") from None
            return self._snapshot(workspace)

    def save(self, workspace: ProjectWorkspace) -> None:
        snapshot = self._snapshot(workspace)
        key = snapshot.session.session_id.casefold()
        with self._lock:
            if key not in self._workspaces:
                raise ConversationNotFound("conversation was not found")
            self._check_message_bound(snapshot)
            self._workspaces[key] = snapshot

    def contains(self, value: object) -> bool:
        with self._lock:
            snapshots = tuple(
                item.model_dump(mode="python") for item in self._workspaces.values()
            )
        return _contains(snapshots, value)

    def _check_message_bound(self, workspace: ProjectWorkspace) -> None:
        if len(workspace.messages) > self._max_messages:
            raise ConversationStateConflict("repository message capacity reached")

    @staticmethod
    def _snapshot(workspace: ProjectWorkspace) -> ProjectWorkspace:
        if not isinstance(workspace, ProjectWorkspace):
            raise TypeError("workspace is invalid")
        return ProjectWorkspace.model_validate(
            copy.deepcopy(workspace.model_dump(mode="python"))
        )


def _contains(container: object, value: object) -> bool:
    if container == value:
        return True
    if isinstance(container, Mapping):
        return any(
            _contains(key, value) or _contains(item, value)
            for key, item in container.items()
        )
    if isinstance(container, Sequence) and not isinstance(
        container,
        (str, bytes, bytearray),
    ):
        return any(_contains(item, value) for item in container)
    return False
