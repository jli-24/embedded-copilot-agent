from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


SExpressionItem: TypeAlias = str | tuple["SExpressionItem", ...]
SExpression: TypeAlias = tuple[SExpressionItem, ...]


@dataclass(frozen=True, slots=True)
class PCBParserLimits:
    max_tokens: int = 1_000_000
    max_depth: int = 128
