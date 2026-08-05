from __future__ import annotations

from ..contracts import FirmwareParserPort, FirmwareProjectSnapshot
from ..exceptions import FirmwareUnavailable


class PlatformIOFirmwareAdapter(FirmwareParserPort):
    def __init__(self, parser: FirmwareParserPort | None = None) -> None:
        self._parser = parser

    def parse(self, firmware_reference: str) -> FirmwareProjectSnapshot:
        if self._parser is None:
            raise FirmwareUnavailable()
        return self._parser.parse(firmware_reference)


__all__ = ["PlatformIOFirmwareAdapter"]
