from __future__ import annotations

import copy
from threading import RLock

from embedded_copilot.experience.existing_contracts import safe_identifier
from embedded_copilot.experience.models import ReviewIntent


class ReviewStateConflict(RuntimeError):
    """A process-local Review Intent cannot be recorded."""


class ProcessLocalReviewRepository:
    """Bounded interaction intents with no Artifact lifecycle ownership."""

    def __init__(self, *, max_intents_per_session: int = 100) -> None:
        if max_intents_per_session < 1:
            raise ValueError("review repository capacity is invalid")
        self._max_intents_per_session = max_intents_per_session
        self._records: dict[str, tuple[ReviewIntent, ...]] = {}
        self._lock = RLock()

    def add(self, intent: ReviewIntent) -> None:
        candidate = self._snapshot(intent)
        key = candidate.session_id.casefold()
        with self._lock:
            records = self._records.get(key, ())
            if candidate.intent_id.casefold() in {
                item.intent_id.casefold() for item in records
            }:
                raise ReviewStateConflict("review intent already exists")
            if len(records) >= self._max_intents_per_session:
                raise ReviewStateConflict("review repository capacity reached")
            self._records[key] = (*records, candidate)

    def list(self, session_id: str) -> tuple[ReviewIntent, ...]:
        key = safe_identifier(session_id, field="session_id").casefold()
        with self._lock:
            return tuple(self._snapshot(item) for item in self._records.get(key, ()))

    @staticmethod
    def _snapshot(intent: ReviewIntent) -> ReviewIntent:
        if not isinstance(intent, ReviewIntent):
            raise TypeError("review intent is invalid")
        return ReviewIntent.model_validate(
            copy.deepcopy(intent.model_dump(mode="python"))
        )
