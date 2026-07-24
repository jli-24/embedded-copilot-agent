from __future__ import annotations

from embedded_copilot.pcb.models import (
    PCBNetType,
    PCBStructureEvidence,
    UnifiedPCBModel,
)


class PCBStructureRuleEngine:
    """Produce deterministic observations without recommendations or scoring."""

    def evaluate(
        self,
        model: UnifiedPCBModel,
    ) -> tuple[PCBStructureEvidence, ...]:
        if not isinstance(model, UnifiedPCBModel):
            raise TypeError("PCB structure model is invalid")
        power_nets = sorted(
            net.name for net in model.nets if net.net_type is PCBNetType.POWER
        )
        ground_nets = sorted(
            net.name for net in model.nets if net.net_type is PCBNetType.GROUND
        )
        power_evidence = (
            (f"Power nets: {', '.join(power_nets)}.",)
            if power_nets
            else ("No power net was identified.",)
        )
        ground_evidence = (
            (f"Ground nets: {', '.join(ground_nets)}.",)
            if ground_nets
            else ("No ground net was identified.",)
        )
        floating = sorted(
            f"{component.reference}.{pin.number} has no assigned net."
            for component in model.components
            for pin in component.pins
            if pin.pad_type.casefold() != "np_thru_hole" and pin.net_name is None
        )
        electrical_count = sum(
            pin.pad_type.casefold() != "np_thru_hole"
            for component in model.components
            for pin in component.pins
        )
        if floating:
            connectivity_outcome = "floating"
            connectivity_evidence = tuple(floating)
        elif electrical_count:
            connectivity_outcome = "connected"
            connectivity_evidence = (
                f"No floating electrical pins were identified across "
                f"{electrical_count} parsed pins.",
            )
        else:
            connectivity_outcome = "missing"
            connectivity_evidence = (
                "No electrical pins were available for connectivity analysis.",
            )
        return (
            PCBStructureEvidence(
                rule_id="pcb-structure-power-net",
                category="power",
                outcome="present" if power_nets else "missing",
                evidence=power_evidence,
            ),
            PCBStructureEvidence(
                rule_id="pcb-structure-ground-net",
                category="ground",
                outcome="present" if ground_nets else "missing",
                evidence=ground_evidence,
            ),
            PCBStructureEvidence(
                rule_id="pcb-structure-floating-pins",
                category="connectivity",
                outcome=connectivity_outcome,
                evidence=connectivity_evidence,
            ),
        )
