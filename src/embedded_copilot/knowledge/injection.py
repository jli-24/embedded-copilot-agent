from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel


CENTRALIZED_KNOWLEDGE_MODE = "supervisor_gateway"
_PROVENANCE_FIELDS = {"id", "title", "source", "category", "score"}
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)", re.I)
_URL_QUERY = re.compile(r"^https?://[^\s]+\?", re.I)
DocumentT = TypeVar("DocumentT", bound=BaseModel)


def extract_centralized_knowledge(
    metadata: Mapping[str, object],
    *,
    field: str,
    model_type: type[DocumentT],
) -> tuple[dict[str, object], list[DocumentT], list[dict[str, object]]] | None:
    copied = copy.deepcopy(dict(metadata))
    if "knowledge_mode" not in copied:
        return None
    if copied.pop("knowledge_mode") != CENTRALIZED_KNOWLEDGE_MODE:
        raise ValueError("centralized knowledge mode is invalid")
    if field not in copied or "knowledge_provenance" not in copied:
        raise ValueError("centralized knowledge input is incomplete")
    raw_documents = copied.pop(field)
    raw_provenance = copied.pop("knowledge_provenance")
    if not isinstance(raw_documents, list):
        raise ValueError("centralized knowledge documents must be a list")
    documents = [
        model_type.model_validate(copy.deepcopy(document))
        for document in raw_documents
    ]
    provenance = _validate_provenance(raw_provenance)
    return copied, documents, provenance


def _validate_provenance(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("centralized knowledge provenance must be a list")
    validated: list[dict[str, object]] = []
    for raw_item in value:
        if not isinstance(raw_item, Mapping) or set(raw_item) != _PROVENANCE_FIELDS:
            raise ValueError("centralized knowledge provenance is invalid")
        item = copy.deepcopy(dict(raw_item))
        for field in ("id", "title", "source", "category"):
            candidate = item[field]
            if not isinstance(candidate, str) or not candidate.strip():
                raise ValueError("centralized knowledge provenance is invalid")
            candidate = candidate.strip()
            if _ABSOLUTE_PATH.match(candidate) or _URL_QUERY.match(candidate):
                raise ValueError("centralized knowledge provenance is unsafe")
            item[field] = candidate
        score = item["score"]
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, (int, float))
        ):
            raise ValueError("centralized knowledge provenance score is invalid")
        validated.append(item)
    return validated
