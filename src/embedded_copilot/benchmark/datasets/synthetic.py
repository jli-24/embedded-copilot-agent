from __future__ import annotations

from embedded_copilot.benchmark.dataset import BenchmarkDataset
from embedded_copilot.benchmark.models import BenchmarkCase
from embedded_copilot.input.models import (
    AttachmentType,
    UnifiedInputContext,
    UserAttachment,
)


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


def create_synthetic_provider_integration_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-provider-integration",
        [
            BenchmarkCase(
                id="synthetic-provider-integration",
                name="Synthetic local provider integration",
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


def create_synthetic_github_provider_dataset() -> BenchmarkDataset:
    return BenchmarkDataset(
        "synthetic-github-provider",
        [
            BenchmarkCase(
                id="synthetic-github-provider",
                name="Synthetic GitHub provider integration",
                category="end_to_end",
                input=(
                    "Design a synthetic ESP32 camera firmware, hardware, "
                    "and PCB workflow."
                ),
                expected={
                    "agents": ["FirmwareAgent", "HardwareAgent", "PCBAgent"],
                    "capabilities": ["firmware", "hardware", "pcb"],
                },
                metadata={
                    "fixture_kind": "synthetic",
                    "required_agents": ["firmware", "hardware", "pcb"],
                },
            )
        ],
    )


def create_synthetic_multimodal_input_dataset() -> BenchmarkDataset:
    cases = [
        BenchmarkCase(
            id="synthetic-input-text",
            name="Synthetic text-only input",
            category="routing",
            input="Generate ESP32 firmware code for GPIO.",
            expected={
                "agents": ["FirmwareAgent"],
                "capabilities": ["firmware"],
            },
            metadata={
                "fixture_kind": "synthetic",
                "_benchmark_input_context": UnifiedInputContext(
                    text="Generate ESP32 firmware code for GPIO."
                ).model_dump(mode="json"),
            },
        ),
        BenchmarkCase(
            id="synthetic-input-image",
            name="Synthetic image attachment input",
            category="routing",
            input="Review ESP32 PCB layout using image attachment metadata.",
            expected={
                "agents": ["PCBAgent"],
                "capabilities": ["pcb"],
            },
            metadata={
                "fixture_kind": "synthetic",
                "_benchmark_input_context": _synthetic_context(
                    attachment_id="image-1",
                    filename="board.png",
                    media_type=AttachmentType.IMAGE,
                    content_type="image/png",
                    size_bytes=128,
                    format_name="png",
                ),
            },
        ),
        BenchmarkCase(
            id="synthetic-input-eda",
            name="Synthetic EDA attachment input",
            category="routing",
            input="Review ESP32 PCB routing constraints using EDA attachment metadata.",
            expected={
                "agents": ["PCBAgent"],
                "capabilities": ["pcb"],
            },
            metadata={
                "fixture_kind": "synthetic",
                "_benchmark_input_context": _synthetic_context(
                    attachment_id="eda-1",
                    filename="board.kicad_pcb",
                    media_type=AttachmentType.EDA,
                    content_type="application/x-kicad-pcb",
                    size_bytes=256,
                    format_name="kicad_pcb",
                ),
            },
        ),
        BenchmarkCase(
            id="synthetic-input-log",
            name="Synthetic log attachment input",
            category="routing",
            input="Debug compile error: undefined reference to app_main.",
            expected={
                "agents": ["DebugAgent"],
                "capabilities": ["debug"],
            },
            metadata={
                "fixture_kind": "synthetic",
                "_benchmark_input_context": _synthetic_context(
                    attachment_id="log-1",
                    filename="serial.log",
                    media_type=AttachmentType.LOG,
                    content_type="text/plain",
                    size_bytes=64,
                    format_name="log",
                ),
            },
        ),
    ]
    return BenchmarkDataset("synthetic-multimodal-input", cases)


def _synthetic_context(
    *,
    attachment_id: str,
    filename: str,
    media_type: AttachmentType,
    content_type: str,
    size_bytes: int,
    format_name: str,
) -> dict[str, object]:
    return UnifiedInputContext(
        attachments=(
            UserAttachment(
                id=attachment_id,
                filename=filename,
                media_type=media_type,
                content_type=content_type,
                size_bytes=size_bytes,
                metadata={
                    "category": media_type.value,
                    "format": format_name,
                },
            ),
        ),
        metadata={"source": "synthetic_fixture"},
    ).model_dump(mode="json")
