from __future__ import annotations

import copy

from .contracts import (
    HardwareSourceReference,
    KiCadParserPort,
    UnifiedHardwareModel,
    validate_unified_hardware_model,
)
from .exceptions import DesignRejected, KiCadUnavailable


class KiCadParserService:
    __slots__ = ("_parser",)

    def __init__(self, parser: KiCadParserPort | None = None) -> None:
        self._parser = parser

    def parse(self, source: HardwareSourceReference) -> UnifiedHardwareModel:
        if self._parser is None:
            raise KiCadUnavailable()
        try:
            checked_source = HardwareSourceReference.model_validate(
                copy.deepcopy(source.model_dump(mode="python"))
            )
            return validate_unified_hardware_model(
                self._parser.parse(copy.deepcopy(checked_source))
            )
        except (KiCadUnavailable, DesignRejected):
            raise
        except Exception as error:
            raise DesignRejected() from error
