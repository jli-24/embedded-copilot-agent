from __future__ import annotations

import copy

from .contracts import MemorySourceKind, MemorySourceProjection, VersionMemoryInput


def extract_source(value: VersionMemoryInput) -> MemorySourceProjection:
    """Return a validated source projection without reading conversational content."""
    if type(value) is not VersionMemoryInput:
        raise TypeError("version memory input must be a typed projection")
    return MemorySourceProjection.model_validate(copy.deepcopy(value.source))


def source_kind(value: VersionMemoryInput) -> MemorySourceKind:
    return extract_source(value).source_type
