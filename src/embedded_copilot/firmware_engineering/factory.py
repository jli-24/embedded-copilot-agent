from .contracts import FirmwareBuildPort, FirmwareDebugAnalyzerPort, FirmwareParserPort
from .service import FirmwareBuildService, FirmwareDebugService, FirmwareEngineeringService


def create_firmware_engineering_service(
    parser: FirmwareParserPort | None = None,
) -> FirmwareEngineeringService:
    return FirmwareEngineeringService(parser)


def create_firmware_build_service(
    port: FirmwareBuildPort | None = None,
) -> FirmwareBuildService:
    return FirmwareBuildService(port)


def create_firmware_debug_service(
    analyzer: FirmwareDebugAnalyzerPort | None = None,
) -> FirmwareDebugService:
    return FirmwareDebugService(analyzer)


__all__ = [
    "create_firmware_build_service",
    "create_firmware_debug_service",
    "create_firmware_engineering_service",
]
