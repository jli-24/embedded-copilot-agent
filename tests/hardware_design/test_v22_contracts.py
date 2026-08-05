import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_design.contracts import (
    HardwareSourceReference,
    validate_unified_hardware_model,
)
from embedded_copilot.hardware_design.models import (
    ComponentProjection,
    DesignSourceType,
    HardwareCapabilitySnapshot,
    InterfaceProjection,
    LayerProjection,
    NetProjection,
    ProjectionStatus,
    UnifiedHardwareModel,
)


def model() -> UnifiedHardwareModel:
    return UnifiedHardwareModel.create(
        project_id="demo",
        design_id="design-1",
        design_source_type=DesignSourceType.KICAD,
        components=(
            ComponentProjection(
                reference="U1",
                value="ESP32",
                footprint=None,
                manufacturer=None,
                part_number=None,
                status=ProjectionStatus.PROJECTED,
            ),
        ),
        nets=(NetProjection(name="GND", connections=("U1.1",), signal_type="POWER"),),
        layers=(LayerProjection(name="F.Cu", layer_type="SIGNAL"),),
        interfaces=(
            InterfaceProjection(name="UART", protocol="UART", signals=("TX", "RX")),
        ),
        constraints=("Review required.",),
        references=("design:design-1",),
    )


def test_unified_model_is_frozen_and_source_bound() -> None:
    value = model()
    assert value.design_source_type is DesignSourceType.KICAD
    assert validate_unified_hardware_model(value) == value
    with pytest.raises(ValidationError):
        value.project_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        UnifiedHardwareModel.model_validate(
            {**value.model_dump(mode="python"), "extra": "x"}
        )


def test_source_reference_rejects_paths_and_unsupported_extensions() -> None:
    with pytest.raises(ValidationError):
        HardwareSourceReference.create(
            project_id="demo",
            design_id="design-1",
            filename="C:/private/demo.kicad_pcb",
            source_type=DesignSourceType.KICAD,
        )
    with pytest.raises(ValidationError):
        HardwareSourceReference.create(
            project_id="demo",
            design_id="design-1",
            filename="demo.txt",
            source_type=DesignSourceType.KICAD,
        )


def test_hardware_capability_snapshot_is_deterministic() -> None:
    first = HardwareCapabilitySnapshot.create(
        project_id="demo",
        parser_available=True,
        review_available=False,
        source_type=DesignSourceType.KICAD,
    )
    second = HardwareCapabilitySnapshot.create(
        project_id="demo",
        parser_available=True,
        review_available=False,
        source_type=DesignSourceType.KICAD,
    )
    assert first == second
