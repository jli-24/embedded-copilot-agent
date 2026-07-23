"""Firmware Foundation interfaces for deterministic mock code generation."""

from embedded_copilot.firmware.agent import FirmwareAgent
from embedded_copilot.firmware.capability import (
    FirmwareCapability,
    FirmwareCapabilityDescriptor,
    register_firmware_foundation,
)
from embedded_copilot.firmware.models import (
    FirmwareRequest,
    GeneratedCode,
    GeneratedFile,
    ValidationResult,
)
from embedded_copilot.firmware.exceptions import (
    FirmwareAnalysisError,
    FirmwareGenerationError,
    FirmwareIntelligenceError,
    FirmwareKnowledgeError,
    FirmwarePlanningError,
    FirmwareProjectError,
)
from embedded_copilot.firmware.generator import FirmwareGenerator
from embedded_copilot.firmware.platform import ESP32Platform, STM32Platform
from embedded_copilot.firmware.project import (
    FirmwareProject,
    FirmwareProjectGenerator,
    FirmwareProjectValidator,
    ProjectFile,
    ProjectTemplateManager,
    ProjectValidationResult,
)
from embedded_copilot.firmware.validator import FirmwareValidator

__all__ = [
    "ESP32Platform",
    "FirmwareAgent",
    "FirmwareAnalysisError",
    "FirmwareCapability",
    "FirmwareCapabilityDescriptor",
    "FirmwareGenerationError",
    "FirmwareGenerator",
    "FirmwareRequest",
    "FirmwareIntelligenceError",
    "FirmwareKnowledgeError",
    "FirmwarePlanningError",
    "FirmwareProject",
    "FirmwareProjectError",
    "FirmwareProjectGenerator",
    "FirmwareProjectValidator",
    "FirmwareValidator",
    "GeneratedCode",
    "GeneratedFile",
    "ProjectFile",
    "ProjectTemplateManager",
    "ProjectValidationResult",
    "STM32Platform",
    "ValidationResult",
    "register_firmware_foundation",
]
