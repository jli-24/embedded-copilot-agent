from __future__ import annotations

from ..contracts import HardwareSourceReference
from ..models import (
    ComponentProjection,
    DesignSourceType,
    HardwareCapabilitySnapshot,
    InterfaceProjection,
    LayerProjection,
    NetProjection,
    ProjectionStatus,
    UnifiedHardwareModel,
)


class FakeKiCadAdapter:
    def parse(self, source: HardwareSourceReference) -> UnifiedHardwareModel:
        return UnifiedHardwareModel.create(
            project_id=source.project_id,
            design_id=source.design_id,
            design_source_type=DesignSourceType.KICAD,
            components=(
                ComponentProjection(
                    reference="U1",
                    value="Projected MCU",
                    footprint=None,
                    manufacturer=None,
                    part_number=None,
                    status=ProjectionStatus.PROJECTED,
                ),
            ),
            nets=(
                NetProjection(
                    name="GND",
                    connections=("U1.1",),
                    signal_type="POWER",
                ),
            ),
            layers=(LayerProjection(name="F.Cu", layer_type="SIGNAL"),),
            interfaces=(
                InterfaceProjection(
                    name="UART",
                    protocol="UART",
                    signals=("TX", "RX"),
                ),
            ),
            constraints=("Design review required before any workspace action.",),
            references=("source:" + source.design_id,),
        )

    def get_capability(self, project_id: str) -> HardwareCapabilitySnapshot:
        return HardwareCapabilitySnapshot.create(
            project_id=project_id,
            parser_available=True,
            review_available=True,
            source_type=DesignSourceType.KICAD,
        )


__all__ = ["FakeKiCadAdapter"]
