from .adapters.serial import SerialObservationAdapter
from .contracts import HardwareObservationPort
from .service import HardwareObservationService


def create_hardware_observation(
    port: HardwareObservationPort | None = None,
) -> HardwareObservationService:
    return HardwareObservationService(port or SerialObservationAdapter())


__all__ = ["create_hardware_observation"]
