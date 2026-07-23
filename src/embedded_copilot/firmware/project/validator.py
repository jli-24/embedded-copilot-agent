from __future__ import annotations

import re
from pathlib import PurePosixPath

from embedded_copilot.firmware.project.models import (
    FirmwareProject,
    ProjectValidationResult,
)


_BASE_REQUIRED_FILES = {
    "esp32": {"main/main.c", "README.md", "CMakeLists.txt"},
    "stm32": {"Core/Src/main.c", "README.md"},
}

_PERIPHERAL_REQUIRED_FILES = {
    ("esp32", "wifi"): {"main/wifi.c", "main/wifi.h"},
    ("esp32", "camera"): {"main/camera.c"},
    ("stm32", "uart"): {"Core/Src/uart.c", "Core/Inc/uart.h"},
}


class FirmwareProjectValidator:
    """Validate an in-memory project without invoking build tools."""

    def validate(self, project: FirmwareProject) -> ProjectValidationResult:
        errors: list[str] = []
        if not project.name.strip():
            errors.append("project name must not be empty")
        if not project.files:
            errors.append("firmware project has no files")

        file_keys: set[str] = set()
        file_paths: set[str] = set()
        for project_file in project.files:
            if not _is_safe_path(project_file.path, allow_directory=False):
                errors.append(f"unsafe project path: {project_file.path}")
            key = project_file.path.casefold()
            if key in file_keys:
                errors.append(f"duplicate project file path: {project_file.path}")
            file_keys.add(key)
            file_paths.add(project_file.path)
            if not project_file.content.strip():
                errors.append(f"empty project file: {project_file.path}")

        structure_keys: set[str] = set()
        structure_node_types: dict[str, str] = {}
        for entry in project.structure:
            if not _is_safe_path(entry, allow_directory=True):
                errors.append(f"unsafe project path: {entry}")
            key = entry.casefold()
            if key in structure_keys:
                errors.append(f"duplicate project structure path: {entry}")
            structure_keys.add(key)
            node_key = entry.rstrip("/").casefold()
            node_type = "directory" if entry.endswith("/") else "file"
            previous_type = structure_node_types.get(node_key)
            if previous_type is not None and previous_type != node_type:
                errors.append(f"project file/directory path conflict: {entry}")
            structure_node_types[node_key] = node_type

        structure_files = {entry for entry in project.structure if not entry.endswith("/")}
        if structure_files != file_paths:
            errors.append("project structure file entries do not match project files")

        structure_directories = {
            entry for entry in project.structure if entry.endswith("/")
        }
        for path in file_paths:
            for directory in _parent_directories(path):
                if directory not in structure_directories:
                    errors.append(f"missing project structure directory: {directory}")

        platform_key = project.platform.casefold()
        required_files = set(_BASE_REQUIRED_FILES.get(platform_key, set()))
        if platform_key not in _BASE_REQUIRED_FILES:
            errors.append(f"unsupported project platform: {project.platform}")

        peripherals = project.metadata.get("peripherals", [])
        if not isinstance(peripherals, list) or any(
            not isinstance(item, str) for item in peripherals
        ):
            errors.append("project metadata peripherals must be a list of strings")
        else:
            for peripheral in peripherals:
                required_files.update(
                    _PERIPHERAL_REQUIRED_FILES.get(
                        (platform_key, peripheral.casefold()), set()
                    )
                )

        for required in sorted(required_files):
            if required not in file_paths:
                errors.append(f"missing required project file: {required}")

        return ProjectValidationResult(
            success=not errors,
            errors=errors,
            metadata={
                "file_count": len(project.files),
                "structure_count": len(project.structure),
            },
        )


def _is_safe_path(path: str, *, allow_directory: bool) -> bool:
    if not path or "\\" in path or re.match(r"^[A-Za-z]:", path):
        return False
    candidate = path[:-1] if allow_directory and path.endswith("/") else path
    if not candidate or candidate.startswith("/"):
        return False
    raw_parts = candidate.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False
    pure_path = PurePosixPath(candidate)
    return not pure_path.is_absolute()


def _parent_directories(path: str) -> list[str]:
    parts = PurePosixPath(path).parts[:-1]
    return ["/".join(parts[:index]) + "/" for index in range(1, len(parts) + 1)]
