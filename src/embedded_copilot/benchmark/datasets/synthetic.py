from __future__ import annotations

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase


def create_synthetic_foundation_dataset() -> BenchmarkDataset:
    fixture_metadata = {"fixture_kind": "synthetic"}
    cases = [
        BenchmarkCase(
            id="synthetic-routing",
            name="Synthetic routing chain",
            category="routing",
            input="Plan a synthetic firmware, hardware, and PCB workflow.",
            expected={
                "agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
                "capabilities": ["firmware", "hardware", "pcb"],
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-firmware",
            name="Synthetic firmware structure",
            category="firmware",
            input="Prepare a synthetic ESP32 project structure for an I2C sensor.",
            expected={
                "platform": "ESP32",
                "components": ["sensor", "I2C"],
                "templates": ["main/main.c"],
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-hardware",
            name="Synthetic hardware plan",
            category="hardware",
            input="Plan synthetic ESP32 hardware with an I2C sensor.",
            expected={
                "component_keywords": ["sensor"],
                "interfaces": ["I2C"],
                "constraint_keywords": ["3.3V"],
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-pcb",
            name="Synthetic PCB review",
            category="pcb",
            input="Review synthetic PCB requirements for power and decoupling.",
            expected={
                "rules": ["PCB-DECOUPLING-001"],
                "issue_ids": [],
                "severities": {},
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-debug",
            name="Synthetic debug classification",
            category="debug",
            input="Classify a synthetic compile failure marker.",
            expected={
                "error_type": "compile_error",
                "finding_ids": ["DBG-COMPILE-MISSING-SYMBOL"],
                "recommendation_keywords": ["symbol"],
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-knowledge",
            name="Synthetic knowledge ranking",
            category="knowledge",
            input="Retrieve the synthetic peripheral reference.",
            expected={
                "ranked_ids": ["synthetic-reference"],
                "sources": {"synthetic-reference": "LOCAL"},
            },
            metadata=fixture_metadata,
        ),
        BenchmarkCase(
            id="synthetic-end-to-end",
            name="Synthetic complete chain",
            category="end_to_end",
            input="Run a synthetic firmware, hardware, and PCB planning chain.",
            expected={
                "agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
                "capabilities": ["firmware", "hardware", "pcb"],
            },
            metadata=fixture_metadata,
        ),
    ]
    return BenchmarkDataset("synthetic-foundation", cases)


def create_synthetic_knowledge_injection_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-knowledge-injection",
        [
            BenchmarkCase(
                id="synthetic-knowledge-injection",
                name="Synthetic centralized knowledge injection",
                category="end_to_end",
                input=(
                    "Design a synthetic ESP32 ESP-IDF camera system with firmware "
                    "code, hardware components, PCB layout, and inspect compile "
                    "error undefined reference to camera_init."
                ),
                expected={
                    "agents": [
                        "FirmwareAgent",
                        "HardwareAgent",
                        "PCBAgent",
                        "DebugAgent",
                    ],
                    "capabilities": ["firmware", "hardware", "pcb", "debug"],
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "required_agents": [
                        "firmware",
                        "hardware",
                        "pcb",
                        "debug",
                    ],
                },
            )
        ],
    )
