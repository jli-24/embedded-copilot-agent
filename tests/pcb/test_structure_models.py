from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from embedded_copilot.pcb.models import (
    PCBComponent,
    PCBLayer,
    PCBNet,
    PCBNetNode,
    PCBNetType,
    PCBPin,
    PCBPosition,
    PCBTrack,
    PCBVia,
    PCBZone,
    UnifiedPCBModel,
)


def _model_payload() -> dict[str, object]:
    return {
        "board_name": "esp32_demo",
        "source_format": "kicad_pcb",
        "components": [
            {
                "reference": "U1",
                "value": "ESP32-S3",
                "footprint": "QFN-56",
                "library": "Package_DFN_QFN",
                "position": {"x_mm": 10.0, "y_mm": 20.0},
                "rotation": 90.0,
                "layer": "F.Cu",
                "pins": [
                    {
                        "number": "1",
                        "pad_type": "smd",
                        "net_name": "GND",
                    }
                ],
            }
        ],
        "nets": [
            {
                "name": "GND",
                "net_type": "ground",
                "nodes": [{"reference": "U1", "pin": "1"}],
            }
        ],
        "layers": [{"name": "F.Cu", "index": 0, "type": "signal"}],
        "tracks": [
            {
                "start": {"x_mm": 1.0, "y_mm": 2.0},
                "end": {"x_mm": 3.0, "y_mm": 4.0},
                "width_mm": 0.25,
                "layer": "F.Cu",
                "net_name": "GND",
            }
        ],
        "vias": [
            {
                "position": {"x_mm": 3.0, "y_mm": 4.0},
                "diameter_mm": 0.8,
                "drill_mm": 0.4,
                "layers": ["F.Cu", "B.Cu"],
                "net_name": "GND",
            }
        ],
        "zones": [
            {
                "name": "Ground fill",
                "net_name": "GND",
                "layers": ["F.Cu"],
            }
        ],
        "metadata": {"generator": "pcbnew", "format_version": 20240108},
    }


def test_unified_pcb_model_builds_typed_immutable_structure() -> None:
    model = UnifiedPCBModel.model_validate(_model_payload())

    assert model.source_format == "kicad_pcb"
    assert isinstance(model.components, tuple)
    assert isinstance(model.components[0], PCBComponent)
    assert isinstance(model.components[0].position, PCBPosition)
    assert isinstance(model.components[0].pins, tuple)
    assert isinstance(model.components[0].pins[0], PCBPin)
    assert isinstance(model.nets[0], PCBNet)
    assert model.nets[0].net_type is PCBNetType.GROUND
    assert isinstance(model.nets[0].nodes[0], PCBNetNode)
    assert isinstance(model.layers[0], PCBLayer)
    assert isinstance(model.tracks[0], PCBTrack)
    assert isinstance(model.vias[0], PCBVia)
    assert isinstance(model.zones[0], PCBZone)
    assert model.model_dump(mode="json")["components"][0]["reference"] == "U1"


def test_unified_pcb_model_deep_copies_and_freezes_nested_state() -> None:
    payload = _model_payload()
    model = UnifiedPCBModel.model_validate(payload)

    payload["components"][0]["pins"][0]["net_name"] = "PRIVATE_MUTATION"
    payload["metadata"]["generator"] = "PRIVATE_MUTATION"

    assert model.components[0].pins[0].net_name == "GND"
    assert model.metadata["generator"] == "pcbnew"
    with pytest.raises(ValidationError):
        model.board_name = "changed"
    with pytest.raises(ValidationError):
        model.components[0].reference = "U2"
    with pytest.raises(TypeError):
        model.metadata["generator"] = "changed"


def test_unified_pcb_model_forbids_extra_and_mutable_metadata() -> None:
    payload = _model_payload()
    payload["unsupported"] = True
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["metadata"] = {"nested": {"mutable": True}}
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["metadata"] = {"bad_number": math.inf}
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["metadata"] = {"origin": "C:/Users/private/board.kicad_pcb"}
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["metadata"] = {"source_path": "boards/demo.kicad_pcb"}
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)


def test_unified_pcb_model_requires_unique_references_layers_and_nets() -> None:
    payload = _model_payload()
    payload["components"].append(payload["components"][0].copy())
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["layers"].append({"name": "B.Cu", "index": 0, "type": "signal"})
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)

    payload = _model_payload()
    payload["nets"].append(
        {"name": "gnd", "net_type": "ground", "nodes": []}
    )
    with pytest.raises(ValidationError):
        UnifiedPCBModel.model_validate(payload)
