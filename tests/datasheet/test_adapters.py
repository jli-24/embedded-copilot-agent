from __future__ import annotations

import copy

import pytest

from embedded_copilot.datasheet.adapters import (
    to_firmware_document,
    to_hardware_document,
    to_pcb_rule_document,
)
from embedded_copilot.datasheet.exceptions import DatasheetAdapterError
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument


def _payload(part_number: str = "ESP32-S3") -> dict[str, object]:
    return {
        "component": {
            "manufacturer": (
                "Espressif" if part_number.startswith("ESP32") else "STMicroelectronics"
            ),
            "part_number": part_number,
            "category": "MCU",
            "package": "QFN-56" if part_number.startswith("ESP32") else "LQFP-100",
            "description": "Deterministic MCU evidence",
        },
        "pins": [
            {
                "number": "1",
                "name": "TX",
                "type": "output",
                "description": "UART transmit",
            }
        ],
        "interfaces": [
            {"name": "UART1", "protocol": "UART", "pins": ["1"]}
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
        "metadata": {"format": "markdown", "record_count": 3},
    }


def test_adapter_creates_deterministic_existing_domain_documents() -> None:
    model = UnifiedDatasheetModel.model_validate(_payload())

    first = (
        to_hardware_document(model),
        to_pcb_rule_document(model),
        to_firmware_document(model),
    )
    second = (
        to_hardware_document(model),
        to_pcb_rule_document(model),
        to_firmware_document(model),
    )

    assert isinstance(first[0], HardwareDocument)
    assert isinstance(first[1], PCBRuleDocument)
    assert isinstance(first[2], FirmwareDocument)
    assert [item.model_dump_json() for item in first] == [
        item.model_dump_json() for item in second
    ]
    assert len({item.id for item in first}) == 3
    assert first[0].vendor == "Espressif"
    assert first[2].platform == "ESP32"
    assert first[2].framework == "ESP-IDF"

    for document in first:
        assert document.metadata["source_kind"] == "structured_datasheet"
        assert document.metadata["part_number"] == "ESP32-S3"
        assert "component_name" not in document.metadata
        assert "peripheral" not in document.metadata
        assert "recommendation" not in document.content.casefold()
        assert "candidate" not in document.content.casefold()


def test_adapter_rejects_fake_payload_and_isolates_source_state() -> None:
    payload = _payload()
    model = UnifiedDatasheetModel.model_validate(payload)
    document = to_hardware_document(model)

    payload["component"]["part_number"] = "MUTATED"  # type: ignore[index]
    payload["interfaces"][0]["pins"].append("99")  # type: ignore[index,union-attr]

    assert document.metadata["part_number"] == "ESP32-S3"
    assert "MUTATED" not in document.content
    assert "99" not in document.content

    for adapter in (
        to_hardware_document,
        to_pcb_rule_document,
        to_firmware_document,
    ):
        with pytest.raises(DatasheetAdapterError):
            adapter(copy.deepcopy(_payload()))  # type: ignore[arg-type]


def test_firmware_adapter_maps_stm32_without_selection_logic() -> None:
    document = to_firmware_document(
        UnifiedDatasheetModel.model_validate(_payload("STM32F407VG"))
    )

    assert document.platform == "STM32"
    assert document.framework == "HAL"
    assert document.metadata["manufacturer"] == "STMicroelectronics"
