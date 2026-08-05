import pytest

from embedded_copilot.hardware_design.adapters.fake import FakeKiCadAdapter
from embedded_copilot.hardware_design.adapters.kicad import KiCadAdapter
from embedded_copilot.hardware_design.contracts import HardwareSourceReference
from embedded_copilot.hardware_design.exceptions import KiCadUnavailable
from embedded_copilot.hardware_design.models import DesignSourceType


def source() -> HardwareSourceReference:
    return HardwareSourceReference.create(
        project_id="demo",
        design_id="design-1",
        filename="demo.kicad_pcb",
        source_type=DesignSourceType.KICAD,
    )


def test_fake_kicad_is_deterministic_100_times() -> None:
    adapter = FakeKiCadAdapter()
    values = [adapter.parse(source()) for _ in range(100)]
    assert all(value == values[0] for value in values)


def test_kicad_adapter_is_unavailable_without_parser() -> None:
    with pytest.raises(KiCadUnavailable):
        KiCadAdapter().parse(source())
