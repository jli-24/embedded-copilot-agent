"""Structured mock firmware project generation interfaces."""

from embedded_copilot.firmware.project.models import (
    FirmwareProject,
    ProjectFile,
    ProjectValidationResult,
)
from embedded_copilot.firmware.project.generator import FirmwareProjectGenerator
from embedded_copilot.firmware.project.templates import (
    ProjectTemplateManager,
    create_default_project_template_manager,
)
from embedded_copilot.firmware.project.validator import FirmwareProjectValidator

__all__ = [
    "FirmwareProject",
    "FirmwareProjectGenerator",
    "FirmwareProjectValidator",
    "ProjectFile",
    "ProjectTemplateManager",
    "ProjectValidationResult",
    "create_default_project_template_manager",
]
