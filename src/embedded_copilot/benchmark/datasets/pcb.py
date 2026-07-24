from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase


@dataclass(frozen=True, slots=True)
class SyntheticPCBFixture:
    filename: str
    content: str


_SIMPLE_ESP32 = """(kicad_pcb
  (version 20240108)
  (generator pcbnew)
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
  (net 1 "GND")
  (net 2 "+3V3")
  (footprint "Package_DFN_QFN:QFN-56"
    (layer "F.Cu")
    (at 10 10)
    (property "Reference" "U1")
    (property "Value" "ESP32-S3")
    (pad "1" smd rect (at 0 0) (size 0.3 0.8) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 0.3 0.8) (layers "F.Cu") (net 2 "+3V3"))
  )
)"""

_POWER_ISSUE = """(kicad_pcb
  (version 20240108)
  (generator pcbnew)
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
  (net 1 "GND")
  (footprint "Package_DFN_QFN:QFN-56"
    (layer "F.Cu")
    (at 10 10)
    (property "Reference" "U1")
    (property "Value" "ESP32-S3")
    (pad "1" smd rect (at 0 0) (size 0.3 0.8) (layers "F.Cu") (net 1 "GND"))
  )
)"""

_FLOATING_NET = """(kicad_pcb
  (version 20240108)
  (generator pcbnew)
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
  (net 1 "GND")
  (net 2 "+3V3")
  (footprint "Package_DFN_QFN:QFN-56"
    (layer "F.Cu")
    (at 10 10)
    (property "Reference" "U1")
    (property "Value" "ESP32-S3")
    (pad "1" smd rect (at 0 0) (size 0.3 0.8) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 0.3 0.8) (layers "F.Cu"))
  )
)"""


SYNTHETIC_PCB_FIXTURES = MappingProxyType(
    {
        "simple-esp32": SyntheticPCBFixture(
            filename="simple-esp32.kicad_pcb",
            content=_SIMPLE_ESP32,
        ),
        "power-issue": SyntheticPCBFixture(
            filename="power-issue.kicad_pcb",
            content=_POWER_ISSUE,
        ),
        "floating-net": SyntheticPCBFixture(
            filename="floating-net.kicad_pcb",
            content=_FLOATING_NET,
        ),
    }
)


def create_synthetic_pcb_intelligence_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-pcb-intelligence",
        [
            BenchmarkCase(
                id="synthetic-pcb-simple-esp32",
                name="Synthetic simple ESP32 PCB",
                category="pcb",
                input="Review the parsed synthetic ESP32 PCB structure.",
                expected={
                    "rules": [
                        "pcb-structure-power-net",
                        "pcb-structure-ground-net",
                        "pcb-structure-floating-pins",
                    ],
                    "issue_ids": [],
                    "severities": {},
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "pcb_fixture_id": "simple-esp32",
                },
            ),
            BenchmarkCase(
                id="synthetic-pcb-power-issue",
                name="Synthetic PCB missing power net",
                category="pcb",
                input="Review the parsed synthetic PCB power structure.",
                expected={
                    "rules": [
                        "pcb-structure-power-net",
                        "pcb-structure-ground-net",
                        "pcb-structure-floating-pins",
                    ],
                    "issue_ids": ["pcb-structure-power-net"],
                    "severities": {"pcb-structure-power-net": "warning"},
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "pcb_fixture_id": "power-issue",
                },
            ),
            BenchmarkCase(
                id="synthetic-pcb-floating-net",
                name="Synthetic PCB floating pin",
                category="pcb",
                input="Review the parsed synthetic PCB connectivity structure.",
                expected={
                    "rules": [
                        "pcb-structure-power-net",
                        "pcb-structure-ground-net",
                        "pcb-structure-floating-pins",
                    ],
                    "issue_ids": ["pcb-structure-floating-pins"],
                    "severities": {"pcb-structure-floating-pins": "warning"},
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "pcb_fixture_id": "floating-net",
                },
            ),
        ],
    )
