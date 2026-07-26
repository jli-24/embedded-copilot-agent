from __future__ import annotations

import hashlib
import json

from embedded_copilot.context_runtime.contracts import (
    ContextReference,
    EngineeringContextRequest,
)
from embedded_copilot.context_runtime.exceptions import EngineeringContextConflict


def canonical_context_id(request: EngineeringContextRequest) -> str:
    payload = json.dumps(
        {
            "session_id": request.session_id,
            "task_intent": request.task_intent,
            "reference_ids": request.reference_ids,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"context:{hashlib.sha256(payload).hexdigest()[:24]}"


def order_resolved_references(
    request: EngineeringContextRequest,
    references: tuple[ContextReference, ...],
) -> tuple[ContextReference, ...]:
    by_id: dict[str, ContextReference] = {}
    for reference in references:
        key = reference.reference_id.casefold()
        if key in by_id:
            raise EngineeringContextConflict()
        by_id[key] = reference
    requested = tuple(reference.casefold() for reference in request.reference_ids)
    if set(by_id) != set(requested):
        raise EngineeringContextConflict()
    return tuple(by_id[reference_id] for reference_id in requested)
