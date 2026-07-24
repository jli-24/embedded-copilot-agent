from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from embedded_copilot.datasheet.models import (
    DatasheetComponent,
    DatasheetElectricalSpec,
    DatasheetInterface,
    DatasheetPin,
    UnifiedDatasheetModel,
)


def _payload() -> dict[str, object]:
    return {
        "component": {
            "manufacturer": " Espressif ",
            "part_number": " ESP32-S3 ",
            "category": " MCU ",
            "package": " QFN-56 ",
            "description": " Wi-Fi and Bluetooth MCU ",
        },
        "pins": [
            {
                "number": "43",
                "name": "U0TXD",
                "type": "output",
                "description": "UART transmit",
            },
            {
                "number": "44",
                "name": "U0RXD",
                "type": "input",
                "description": "UART receive",
            },
        ],
        "interfaces": [
            {"name": "UART0", "protocol": "uart", "pins": ["43", "44"]}
        ],
        "electrical_specs": [
            {
                "parameter": "Supply voltage",
                "min_value": 3.0,
                "typical_value": 3.3,
                "max_value": 3.6,
                "unit": "V",
            }
        ],
        "power_requirements": [
            {
                "parameter": "Supply voltage",
                "min_value": 3.0,
                "typical_value": 3.3,
                "max_value": 3.6,
                "unit": "V",
            }
        ],
        "metadata": {"format": "markdown", "record_count": 4},
    }


def test_unified_datasheet_model_isolates_and_freezes_nested_state() -> None:
    payload = _payload()
    model = UnifiedDatasheetModel.model_validate(payload)

    assert isinstance(model.pins, tuple)
    assert isinstance(model.interfaces, tuple)
    assert isinstance(model.interfaces[0].pins, tuple)
    assert isinstance(model.electrical_specs, tuple)
    assert model.component.manufacturer == "Espressif"
    assert model.interfaces[0].protocol == "UART"

    payload["pins"][0]["name"] = "MUTATED"  # type: ignore[index]
    payload["interfaces"][0]["pins"].append("99")  # type: ignore[index,union-attr]
    payload["metadata"]["format"] = "mutated"  # type: ignore[index]

    assert model.pins[0].name == "U0TXD"
    assert model.interfaces[0].pins == ("43", "44")
    assert model.metadata == {"format": "markdown", "record_count": 4}

    with pytest.raises(ValidationError):
        model.component.part_number = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        model.metadata["format"] = "changed"  # type: ignore[index]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update({"unexpected": True}),
        lambda payload: payload.update({"metadata": {"nested": {"bad": True}}}),
        lambda payload: payload.update({"metadata": {"bad_number": math.inf}}),
        lambda payload: payload.update(
            {"metadata": {"source_path": "datasheets/part.md"}}
        ),
        lambda payload: payload.update(
            {"metadata": {"origin": "C:/Users/private/part.md"}}
        ),
        lambda payload: payload["component"].update(
            {"description": "C:/Users/private/full-datasheet.txt"}
        ),
        lambda payload: payload["component"].update(
            {"description": "MCU source C:\\Users\\private\\datasheet.txt"}
        ),
    ],
)
def test_unified_datasheet_model_rejects_unsafe_state(mutation) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)


def test_unified_datasheet_model_validates_electrical_and_pin_relations() -> None:
    payload = _payload()
    payload["pins"].append(dict(payload["pins"][0]))  # type: ignore[index,union-attr]
    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)

    payload = _payload()
    payload["interfaces"][0]["pins"] = ["404"]  # type: ignore[index]
    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)

    with pytest.raises(ValidationError):
        DatasheetElectricalSpec(
            parameter="Supply voltage",
            min_value=3.6,
            typical_value=3.3,
            max_value=3.0,
            unit="V",
        )

    with pytest.raises(ValidationError):
        DatasheetElectricalSpec(
            parameter="Supply current",
            min_value=None,
            typical_value=None,
            max_value=None,
            unit="A",
        )


def test_unified_datasheet_model_requires_engineering_evidence() -> None:
    payload = _payload()
    payload["pins"] = []
    payload["interfaces"] = []
    payload["electrical_specs"] = []
    payload["power_requirements"] = []

    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)


def test_unified_datasheet_model_rejects_conflicting_specs_and_noncanonical_units() -> None:
    payload = _payload()
    conflict = dict(payload["electrical_specs"][0])  # type: ignore[index]
    conflict["max_value"] = 3.7
    payload["electrical_specs"].append(conflict)  # type: ignore[union-attr]
    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)

    payload = _payload()
    payload["electrical_specs"][0]["unit"] = "mA"  # type: ignore[index]
    payload["power_requirements"][0]["unit"] = "mA"  # type: ignore[index]
    with pytest.raises(ValidationError):
        UnifiedDatasheetModel.model_validate(payload)


def test_datasheet_models_forbid_extra_fields() -> None:
    constructors = (
        lambda: DatasheetComponent(
            manufacturer="STMicroelectronics",
            part_number="STM32F407VG",
            category="MCU",
            package="LQFP-100",
            description="Arm Cortex-M4 MCU",
            extra_field=True,
        ),
        lambda: DatasheetPin(
            number="1",
            name="VDD",
            type="power",
            description="Supply",
            extra_field=True,
        ),
        lambda: DatasheetInterface(
            name="SPI1",
            protocol="SPI",
            pins=("1",),
            extra_field=True,
        ),
    )

    for construct in constructors:
        with pytest.raises(ValidationError):
            construct()


def test_unified_datasheet_model_serialization_is_deterministic() -> None:
    first = UnifiedDatasheetModel.model_validate(_payload())
    second = UnifiedDatasheetModel.model_validate(_payload())

    assert first.model_dump_json() == second.model_dump_json()
