from __future__ import annotations

import copy
import hashlib
import json

from embedded_copilot.datasheet.exceptions import DatasheetAdapterError
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.hardware.knowledge.models import HardwareDocument
from embedded_copilot.pcb.knowledge.models import PCBRuleDocument


def to_hardware_document(model: UnifiedDatasheetModel) -> HardwareDocument:
    validated = _copy_model(model)
    try:
        return HardwareDocument(
            id=_document_id(validated, "hardware"),
            title=_title(validated, "hardware"),
            category="datasheet_component",
            vendor=validated.component.manufacturer,
            content=_canonical_content(
                {
                    "component": validated.component.model_dump(mode="json"),
                    "electrical_specs": [
                        item.model_dump(mode="json")
                        for item in validated.electrical_specs
                    ],
                    "interfaces": [
                        item.model_dump(mode="json") for item in validated.interfaces
                    ],
                    "pins": [item.model_dump(mode="json") for item in validated.pins],
                    "power_requirements": [
                        item.model_dump(mode="json")
                        for item in validated.power_requirements
                    ],
                }
            ),
            metadata=_metadata(validated),
        )
    except Exception:
        raise DatasheetAdapterError("Datasheet hardware adaptation failed") from None


def to_pcb_rule_document(model: UnifiedDatasheetModel) -> PCBRuleDocument:
    validated = _copy_model(model)
    try:
        return PCBRuleDocument(
            id=_document_id(validated, "pcb"),
            title=_title(validated, "PCB"),
            category="datasheet_constraint",
            content=_canonical_content(
                {
                    "component": {
                        "manufacturer": validated.component.manufacturer,
                        "package": validated.component.package,
                        "part_number": validated.component.part_number,
                    },
                    "interfaces": [
                        item.model_dump(mode="json") for item in validated.interfaces
                    ],
                    "pins": [item.model_dump(mode="json") for item in validated.pins],
                    "power_requirements": [
                        item.model_dump(mode="json")
                        for item in validated.power_requirements
                    ],
                }
            ),
            metadata=_metadata(validated),
        )
    except Exception:
        raise DatasheetAdapterError("Datasheet PCB adaptation failed") from None


def to_firmware_document(model: UnifiedDatasheetModel) -> FirmwareDocument:
    validated = _copy_model(model)
    try:
        platform, framework = _firmware_scope(validated.component.part_number)
        return FirmwareDocument(
            id=_document_id(validated, "firmware"),
            title=_title(validated, "firmware"),
            platform=platform,
            framework=framework,
            content=_canonical_content(
                {
                    "component": {
                        "manufacturer": validated.component.manufacturer,
                        "part_number": validated.component.part_number,
                    },
                    "electrical_specs": [
                        item.model_dump(mode="json")
                        for item in validated.electrical_specs
                    ],
                    "interfaces": [
                        item.model_dump(mode="json") for item in validated.interfaces
                    ],
                    "pins": [item.model_dump(mode="json") for item in validated.pins],
                }
            ),
            metadata=_metadata(validated),
        )
    except Exception:
        raise DatasheetAdapterError("Datasheet firmware adaptation failed") from None


def _copy_model(model: UnifiedDatasheetModel) -> UnifiedDatasheetModel:
    if not isinstance(model, UnifiedDatasheetModel):
        raise DatasheetAdapterError("Datasheet adapter input is invalid")
    try:
        return UnifiedDatasheetModel.model_validate(
            copy.deepcopy(model.model_dump(mode="python"))
        )
    except Exception:
        raise DatasheetAdapterError("Datasheet adapter input is invalid") from None


def _canonical_content(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _document_id(model: UnifiedDatasheetModel, domain: str) -> str:
    identity = "\x00".join(
        (
            domain,
            model.component.manufacturer.casefold(),
            model.component.part_number.casefold(),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"datasheet-{domain}-{digest}"


def _title(model: UnifiedDatasheetModel, domain: str) -> str:
    return (
        f"{model.component.manufacturer} {model.component.part_number} "
        f"Datasheet {domain} evidence"
    )


def _metadata(model: UnifiedDatasheetModel) -> dict[str, str | int]:
    return {
        "electrical_spec_count": len(model.electrical_specs),
        "interface_count": len(model.interfaces),
        "manufacturer": model.component.manufacturer,
        "part_number": model.component.part_number,
        "pin_count": len(model.pins),
        "source_kind": "structured_datasheet",
    }


def _firmware_scope(part_number: str) -> tuple[str, str]:
    normalized = part_number.casefold()
    if normalized.startswith("esp32"):
        return "ESP32", "ESP-IDF"
    if normalized.startswith("stm32"):
        return "STM32", "HAL"
    return part_number, "datasheet"
