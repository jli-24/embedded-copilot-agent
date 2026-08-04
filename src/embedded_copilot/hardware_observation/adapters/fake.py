from ..contracts import (
    BootStatus,
    HardwareObservationPort,
    HealthStatus,
    ObservationSnapshot,
)


class FakeObservationAdapter(HardwareObservationPort):
    def read(self, device_reference: str) -> ObservationSnapshot:
        return ObservationSnapshot.create(
            device_id=device_reference,
            boot_status=BootStatus.BOOTED,
            firmware_version="PROJECTED",
            health_status=HealthStatus.HEALTHY,
            error_summary="",
        )


__all__ = ["FakeObservationAdapter"]
