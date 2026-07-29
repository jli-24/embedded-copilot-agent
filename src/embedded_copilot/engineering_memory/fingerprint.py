from __future__ import annotations

import copy
import hashlib
import json

from pydantic import BaseModel


def canonical_fingerprint(value: BaseModel) -> str:
    validated = type(value).model_validate(copy.deepcopy(value))
    encoded = json.dumps(
        validated.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def canonical_data_fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
