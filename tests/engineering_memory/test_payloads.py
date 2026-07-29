from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from embedded_copilot.engineering_memory.models import (
    BoardProfileMemory,
    ComponentMemory,
    EngineeringDecisionMemory,
    InterfaceBindingMemory,
    KnownIssueMemory,
    KnownIssueSeverity,
    MemoryPayload,
    MemoryProvenance,
    MemorySourceType,
    MemoryType,
    PinBindingMemory,
    PowerConstraintMemory,
    VerificationHistoryMemory,
)
from embedded_copilot.engineering_memory.rules import logical_key_for
from embedded_copilot.verification_agent import (
    VerificationStatus,
    VerificationSubjectType,
)

UTC_TIME = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def _payloads() -> tuple[object, ...]:
    return (
        BoardProfileMemory(
            memory_type=MemoryType.BOARD_PROFILE,
            board_id="board-1",
            board_name="Sensor Board",
            mcu_family="STM32",
            mcu_model="STM32F407VG",
            architecture="ARM Cortex-M4",
        ),
        ComponentMemory(
            memory_type=MemoryType.COMPONENT,
            component_reference="U1",
            component_type="MCU",
            part_number="STM32F407VG",
            manufacturer="STMicroelectronics",
            quantity=1,
        ),
        PinBindingMemory(
            memory_type=MemoryType.PIN_BINDING,
            target_id="mcu-1",
            pin_id="PB7",
            function="I2C1_SDA",
            component_reference="U1",
            interface_reference="i2c-1",
        ),
        InterfaceBindingMemory(
            memory_type=MemoryType.INTERFACE_BINDING,
            target_id="mcu-1",
            interface_id="i2c-1",
            signal="SDA",
            pin_id="PB7",
            component_reference="U1",
        ),
        PowerConstraintMemory(
            memory_type=MemoryType.POWER_CONSTRAINT,
            supply_id="rail-3v3",
            load_id="U1",
            minimum_voltage_mv=3000,
            maximum_voltage_mv=3600,
            maximum_current_ma=500,
        ),
        EngineeringDecisionMemory(
            memory_type=MemoryType.ENGINEERING_DECISION,
            decision_topic="rtos-choice",
            decision="Use FreeRTOS",
            rationale_summary="Existing platform support and deterministic scheduling",
        ),
        KnownIssueMemory(
            memory_type=MemoryType.KNOWN_ISSUE,
            issue_key="i2c-errata-1",
            title="I2C busy flag may remain set",
            severity=KnownIssueSeverity.HIGH,
            description_summary="Busy flag can remain set after an interrupted transfer",
            mitigation_summary="Reset the peripheral before retrying the transfer",
        ),
        VerificationHistoryMemory(
            memory_type=MemoryType.VERIFICATION_HISTORY,
            verification_request_id="verify-1",
            subject_type=VerificationSubjectType.HARDWARE,
            verification_status=VerificationStatus.REVIEW_REQUIRED,
            finding_categories=("POWER_CONSTRAINT", "PIN_CONFLICT"),
            confidence_basis="Deterministic rules found explicit candidate conflicts",
        ),
    )


def test_all_payloads_are_closed_frozen_contracts() -> None:
    payloads = _payloads()
    assert tuple(item.memory_type for item in payloads) == tuple(MemoryType)
    for payload in payloads:
        with pytest.raises(ValidationError):
            type(payload)(**payload.model_dump(), extra_field="forbidden")
        with pytest.raises(ValidationError):
            payload.memory_type = MemoryType.BOARD_PROFILE


def test_logical_keys_use_only_approved_stable_fields() -> None:
    payloads = _payloads()
    assert tuple(logical_key_for(item) for item in payloads) == (
        "board-profile",
        "component:U1",
        "pin:mcu-1:PB7",
        "interface:mcu-1:i2c-1:SDA",
        "power:rail-3v3:U1",
        "decision:rtos-choice",
        "issue:i2c-errata-1",
        "verification:verify-1",
    )
    pin = payloads[2]
    changed_reference = pin.model_copy(update={"component_reference": "U2"})
    changed_function = pin.model_copy(update={"function": "GPIO_OUTPUT"})
    assert logical_key_for(changed_reference) == logical_key_for(pin)
    assert logical_key_for(changed_function) == logical_key_for(pin)


def test_verification_history_accepts_full_v038_request_identity() -> None:
    verification_id = "verification:" + "a" * 147
    payload = VerificationHistoryMemory(
        verification_request_id=verification_id,
        subject_type=VerificationSubjectType.FIRMWARE,
        verification_status=VerificationStatus.PASS,
        confidence_basis="Complete deterministic verification evidence.",
    )
    assert len(verification_id) == 160
    assert logical_key_for(payload) == f"verification:{verification_id}"


def test_provenance_is_safe_immutable_and_utc_normalized() -> None:
    value = MemoryProvenance(
        source_type=MemorySourceType.DATASHEET_RESULT,
        source_reference="datasheet-result-1",
        source_revision="rev-A",
        created_by="caller-1",
        observed_at=UTC_TIME,
    )
    assert value.observed_at == UTC_TIME
    with pytest.raises(ValidationError):
        MemoryProvenance(**value.model_dump() | {"source_reference": "C:/secret.env"})
    with pytest.raises(ValidationError):
        MemoryProvenance(**value.model_dump() | {"source_reference": "secret=token"})


def test_payload_numeric_and_tuple_boundaries_are_strict() -> None:
    with pytest.raises(ValidationError):
        ComponentMemory(**_payloads()[1].model_dump() | {"quantity": True})
    power = _payloads()[4]
    with pytest.raises(ValidationError):
        PowerConstraintMemory(
            **power.model_dump()
            | {"minimum_voltage_mv": 3601, "maximum_voltage_mv": 3600}
        )
    history = _payloads()[7]
    sorted_history = VerificationHistoryMemory(
        **history.model_dump() | {"finding_categories": ("Z_CATEGORY", "A_CATEGORY")}
    )
    assert sorted_history.finding_categories == ("A_CATEGORY", "Z_CATEGORY")
    with pytest.raises(ValidationError):
        VerificationHistoryMemory(
            **history.model_dump()
            | {"finding_categories": ("PIN_CONFLICT", "PIN_CONFLICT")}
        )


def test_memory_payload_union_rejects_incomplete_untyped_dict() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(MemoryPayload).validate_python(
            {"memory_type": "BOARD_PROFILE"}, strict=True
        )
