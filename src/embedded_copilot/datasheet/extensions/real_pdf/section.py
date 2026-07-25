from __future__ import annotations

import re
from dataclasses import dataclass


_WHITESPACE = re.compile(r"[ \t\f\v]+")
_DASHES = str.maketrans({"\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"})


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    number: int
    text: str


def normalize_page_text(text: str) -> str:
    """Normalize layout noise without deleting technical line boundaries."""
    normalized: list[str] = []
    for raw_line in text.translate(_DASHES).replace("\r\n", "\n").split("\n"):
        line = _WHITESPACE.sub(" ", raw_line).strip()
        if line:
            normalized.append(line)
    return "\n".join(normalized)
