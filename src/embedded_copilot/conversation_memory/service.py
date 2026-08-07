from __future__ import annotations

import copy
import hashlib

from .classifier import classify
from .contracts import ConversationMemoryPort, ConversationSnapshot
from .extractor import extract_fields
from .models import ConversationMemoryCandidate, MemoryCandidateStatus
from .ranking import rank_turns


class ConversationMemoryService:
    def extract(self, snapshot: ConversationSnapshot) -> ConversationMemoryCandidate | None:
        if type(snapshot) is not ConversationSnapshot:
            raise TypeError("conversation snapshot must be a typed contract")
        checked = ConversationSnapshot.model_validate(
            copy.deepcopy(snapshot.model_dump(mode="python"))
        )
        ranked = rank_turns(checked.turns)
        if not ranked:
            return None
        selected = ranked[0]
        memory_type = classify(selected.content_summary)
        if memory_type is None:
            return None
        values = extract_fields(
            checked,
            memory_type,
            selected.content_summary,
            selected.references[0] if selected.references else None,
        )
        material = {
            "candidate_id": "candidate-"
            + hashlib.sha256(
                f"{checked.project_id}:{checked.session_id}:{selected.turn_id}".encode()
            ).hexdigest()[:24],
            "project_id": checked.project_id,
            "source_session": checked.session_id,
            "memory_type": memory_type,
            "status": MemoryCandidateStatus.PENDING_REVIEW,
            **values,
        }
        provisional = ConversationMemoryCandidate.model_construct(
            **material, fingerprint="sha256:" + "0" * 64
        )
        from .models import _fingerprint_material

        return ConversationMemoryCandidate.model_validate(
            {**material, "fingerprint": _fingerprint_material(provisional)}
        )


__all__ = ["ConversationMemoryPort", "ConversationMemoryService"]
