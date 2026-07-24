from __future__ import annotations

from embedded_copilot.pcb.models import UnifiedPCBModel
from embedded_copilot.pcb.structure_rules import PCBStructureRuleEngine


def _model(*, floating: bool = False, include_power: bool = True) -> UnifiedPCBModel:
    nets = [
        {"name": "GND", "net_type": "ground", "nodes": []},
    ]
    if include_power:
        nets.append({"name": "+3V3", "net_type": "power", "nodes": []})
    return UnifiedPCBModel(
        board_name="demo",
        source_format="kicad_pcb",
        components=(
            {
                "reference": "U1",
                "value": "ESP32-S3",
                "footprint": "QFN-56",
                "library": "Package_DFN_QFN",
                "position": {"x_mm": 1.0, "y_mm": 2.0},
                "layer": "F.Cu",
                "pins": (
                    {"number": "1", "pad_type": "smd", "net_name": "GND"},
                    {
                        "number": "2",
                        "pad_type": "smd",
                        "net_name": None if floating else "+3V3",
                    },
                    {
                        "number": "MP",
                        "pad_type": "np_thru_hole",
                        "net_name": None,
                    },
                ),
            },
        ),
        nets=tuple(nets),
        layers=(
            {"name": "F.Cu", "index": 0, "type": "signal"},
            {"name": "B.Cu", "index": 31, "type": "signal"},
        ),
    )


def test_structure_rules_are_deterministic_and_evidence_only() -> None:
    model = _model()
    engine = PCBStructureRuleEngine()

    first = engine.evaluate(model)
    second = engine.evaluate(model.model_copy(deep=True))

    assert first == second
    assert [item.rule_id for item in first] == [
        "pcb-structure-power-net",
        "pcb-structure-ground-net",
        "pcb-structure-floating-pins",
    ]
    assert [item.outcome for item in first] == ["present", "present", "connected"]
    serialized = "".join(item.model_dump_json() for item in first)
    assert "recommendation" not in serialized
    assert "severity" not in serialized
    assert "risk" not in serialized


def test_structure_rules_report_missing_power_and_floating_evidence() -> None:
    evidence = PCBStructureRuleEngine().evaluate(
        _model(floating=True, include_power=False)
    )

    assert evidence[0].outcome == "missing"
    assert evidence[0].evidence == ("No power net was identified.",)
    assert evidence[1].outcome == "present"
    assert evidence[2].outcome == "floating"
    assert evidence[2].evidence == ("U1.2 has no assigned net.",)


def test_structure_rules_ignore_non_electrical_mounting_pads() -> None:
    evidence = PCBStructureRuleEngine().evaluate(_model())

    assert evidence[2].outcome == "connected"
    assert "MP" not in " ".join(evidence[2].evidence)


def test_structure_rules_do_not_claim_connectivity_without_electrical_pins() -> None:
    model = UnifiedPCBModel(
        board_name="no_pins",
        source_format="kicad_pcb",
        components=(),
        nets=({"name": "GND", "net_type": "ground", "nodes": ()},),
        layers=({"name": "F.Cu", "index": 0, "type": "signal"},),
    )

    evidence = PCBStructureRuleEngine().evaluate(model)

    assert evidence[2].outcome == "missing"
    assert evidence[2].evidence == (
        "No electrical pins were available for connectivity analysis.",
    )
