from __future__ import annotations

from ..contracts import (
    HardwareSourceReference,
    KiCadParserPort,
    UnifiedHardwareModel,
)
from ..exceptions import KiCadUnavailable


class KiCadAdapter:
    """Bridge only to an explicitly injected KiCad parser."""

    def __init__(self, parser: KiCadParserPort | None = None) -> None:
        self._parser = parser

    def parse(self, source: HardwareSourceReference) -> UnifiedHardwareModel:
        if self._parser is None:
            raise KiCadUnavailable()
        try:
            return self._parser.parse(source)
        except KiCadUnavailable:
            raise
        except Exception as error:
            raise KiCadUnavailable() from error


__all__ = ["KiCadAdapter"]
