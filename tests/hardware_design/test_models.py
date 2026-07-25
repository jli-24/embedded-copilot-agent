from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_design.models import (
    DesignComponent,
    DesignModule,
    GPIOAssignment,
    GPIOAssignmentStatus,
    HardwareDesignBlueprint,
    PowerTree,
)


def _blueprint() -> HardwareDesignBlueprint:
    return HardwareDesignBlueprint(
        project_name="security-terminal",
        target_platform="ESP32",
        modules=(
            DesignModule(
                name="ESP32-S3",
                description="Controller copied from HardwarePlan.",
                source_ids=("datasheet:esp32-s3",),
            ),
        ),
        components=(
            DesignComponent(
                name="PIR",
                category="sensor",
                purpose="Motion sensor copied from HardwarePlan.",
            ),
        ),
        gpio_assignments=(
            GPIOAssignment(
                function="PIR input",
                gpio="GPIO4",
                interface="GPIO",
                reason="Observed in Firmware; hardware correctness is unresolved.",
                status=GPIOAssignmentStatus.UNRESOLVED,
                source_ids=("firmware:main.c#line:12",),
            ),
        ),
        power_tree=PowerTree(
            input="unresolved",
            consumers=("ESP32-S3", "PIR"),
            limitations=("Power topology is unresolved.",),
        ),
        constraints=("Confirm electrical requirements.",),
        limitations=("PIR has no confirmed component evidence.",),
        source_ids=("datasheet:esp32-s3", "firmware:main.c#line:12"),
    )


def test_blueprint_is_deeply_immutable_and_serializable() -> None:
    blueprint = _blueprint()
    restored = HardwareDesignBlueprint.model_validate_json(blueprint.model_dump_json())

    assert isinstance(blueprint.modules, tuple)
    assert isinstance(blueprint.components, tuple)
    assert restored == blueprint
    with pytest.raises(ValidationError):
        blueprint.project_name = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        blueprint.components[0].name = "mutated"  # type: ignore[misc]


def test_blueprint_models_forbid_extra_and_blank_fields() -> None:
    with pytest.raises(ValidationError):
        DesignModule(
            name="ESP32-S3",
            description="Controller.",
            unexpected=True,
        )
    with pytest.raises(ValidationError):
        DesignComponent(name=" ", category="sensor", purpose="PIR")


def test_gpio_status_contract_reserves_assigned_without_implying_it() -> None:
    assert [status.value for status in GPIOAssignmentStatus] == [
        "assigned",
        "conflict",
        "unresolved",
    ]
    assert _blueprint().gpio_assignments[0].status is GPIOAssignmentStatus.UNRESOLVED
