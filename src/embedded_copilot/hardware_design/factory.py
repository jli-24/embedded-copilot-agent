from __future__ import annotations

from .parser import KiCadParserService
from .service import HardwareDesignService


def create_kicad_parser_service(parser=None) -> KiCadParserService:
    return KiCadParserService(parser)


def create_hardware_design_service(port) -> HardwareDesignService:
    return HardwareDesignService(port)


__all__ = ["create_hardware_design_service", "create_kicad_parser_service"]
