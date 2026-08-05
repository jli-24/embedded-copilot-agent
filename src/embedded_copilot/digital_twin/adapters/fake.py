from __future__ import annotations

from ..contracts import (
    ConstraintProjection,
    DigitalTwinPort,
    DigitalTwinSnapshot,
    MetricsProjection,
)


class FakeDigitalTwinAdapter(DigitalTwinPort):
    def get_snapshot(self, project_id: str) -> DigitalTwinSnapshot:
        metrics = MetricsProjection.create(
            cpu_usage="12%",
            memory_usage="34%",
            flash_usage="42%",
            ram_usage="28%",
            latency="5ms",
            power_estimate="120mW",
            communication_quality="GOOD",
        )
        constraint = ConstraintProjection.create(
            constraint_type="POWER",
            reference=f"constraint:{project_id}",
            status="PROJECTED",
        )
        return DigitalTwinSnapshot.create(
            project_id=project_id,
            hardware_reference=f"hardware:{project_id}",
            firmware_reference=f"firmware:{project_id}",
            device_reference=f"device:{project_id}",
            validation_reference=f"validation:{project_id}",
            metrics=metrics,
            constraints=(constraint,),
        )


__all__ = ["FakeDigitalTwinAdapter"]
