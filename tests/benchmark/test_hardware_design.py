from __future__ import annotations

from embedded_copilot.benchmark.datasets.hardware_design import (
    create_smart_security_hardware_plan,
)
from embedded_copilot.hardware_design.projector import project_artifact


def test_smart_security_fixture_is_explicit_and_projection_is_unresolved() -> None:
    plan = create_smart_security_hardware_plan()
    artifact = project_artifact(plan)

    assert plan.mcu == "ESP32-S3"
    assert [item.name for item in plan.components] == [
        "Camera",
        "PIR",
        "MQ-2",
        "SD Card",
        "MQTT",
    ]
    assert [item.name for item in artifact.blueprint.modules] == [
        "ESP32-S3",
        "Camera",
        "PIR",
        "MQ-2",
        "SD Card",
        "MQTT",
    ]
    assert artifact.blueprint.connections == ()
    assert artifact.blueprint.gpio_assignments == ()
    assert artifact.blueprint.power_tree.input == "unresolved"
    assert artifact.evidence == ()
    assert artifact.decisions == ()
    assert all(
        any(name in limitation for limitation in artifact.blueprint.limitations)
        for name in ("ESP32-S3", "Camera", "PIR", "MQ-2", "SD Card", "MQTT")
    )


def test_smart_security_projection_is_deterministic() -> None:
    first = project_artifact(create_smart_security_hardware_plan())
    second = project_artifact(create_smart_security_hardware_plan())

    assert first.model_dump_json() == second.model_dump_json()
