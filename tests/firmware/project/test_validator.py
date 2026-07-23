import pytest

from embedded_copilot.firmware.project.models import FirmwareProject, ProjectFile
from embedded_copilot.firmware.project.validator import FirmwareProjectValidator


def _file(path: str, content: str = "mock/unverified") -> ProjectFile:
    return ProjectFile(path=path, content=content, language="C")


def _esp32_project() -> FirmwareProject:
    return FirmwareProject(
        name="demo",
        platform="ESP32",
        framework="ESP-IDF",
        files=[
            _file("main/main.c"),
            _file("main/wifi.c"),
            _file("main/wifi.h"),
            _file("README.md"),
            _file("CMakeLists.txt"),
        ],
        structure=[
            "main/",
            "main/main.c",
            "main/wifi.c",
            "main/wifi.h",
            "README.md",
            "CMakeLists.txt",
        ],
        metadata={"peripherals": ["WiFi"]},
    )


def test_validator_accepts_complete_project() -> None:
    result = FirmwareProjectValidator().validate(_esp32_project())

    assert result.success is True
    assert result.errors == []
    assert result.metadata["file_count"] == 5


def test_validator_reports_blank_name_and_empty_content() -> None:
    project = _esp32_project().model_copy(
        update={
            "name": "",
            "files": [_file("main/main.c", "")],
            "structure": ["main/", "main/main.c"],
            "metadata": {"peripherals": []},
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert "project name must not be empty" in result.errors
    assert "empty project file: main/main.c" in result.errors


def test_validator_reports_case_insensitive_path_conflicts() -> None:
    project = _esp32_project().model_copy(
        update={
            "files": [_file("main/main.c"), _file("MAIN/Main.c")],
            "structure": ["main/", "main/main.c", "MAIN/Main.c"],
            "metadata": {"peripherals": []},
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert any("duplicate project file path" in error for error in result.errors)


def test_validator_reports_file_directory_path_conflict() -> None:
    project = _esp32_project().model_copy(
        update={"structure": [*_esp32_project().structure, "README.md/"]}
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert any("file/directory path conflict" in error for error in result.errors)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/private/main.c",
        "C:/private/main.c",
        "main\\main.c",
        "main/../main.c",
        "main/./main.c",
        "main//main.c",
    ],
)
def test_validator_rejects_unsafe_paths(unsafe_path: str) -> None:
    project = _esp32_project().model_copy(
        update={
            "files": [_file(unsafe_path)],
            "structure": [unsafe_path],
            "metadata": {"peripherals": []},
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert any("unsafe project path" in error for error in result.errors)


def test_validator_reports_structure_and_required_file_mismatches() -> None:
    project = _esp32_project().model_copy(
        update={
            "files": [_file("main/main.c"), _file("README.md")],
            "structure": ["main/", "main/main.c", "orphan.c"],
            "metadata": {"peripherals": ["WiFi"]},
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert any("structure file entries" in error for error in result.errors)
    assert "missing required project file: CMakeLists.txt" in result.errors
    assert "missing required project file: main/wifi.c" in result.errors
    assert "missing required project file: main/wifi.h" in result.errors


def test_validator_requires_exact_posix_case_between_structure_and_files() -> None:
    project = _esp32_project().model_copy(
        update={
            "structure": [
                "MAIN/",
                "MAIN/MAIN.C",
                "main/wifi.c",
                "main/wifi.h",
                "README.md",
                "CMakeLists.txt",
            ]
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert any("structure file entries" in error for error in result.errors)
    assert "missing project structure directory: main/" in result.errors


def test_validator_requires_exact_case_for_platform_files() -> None:
    project = _esp32_project().model_copy(
        update={
            "files": [
                _file("main/main.c"),
                _file("main/wifi.c"),
                _file("main/wifi.h"),
                _file("readme.md"),
                _file("cmakelists.txt"),
            ],
            "structure": [
                "main/",
                "main/main.c",
                "main/wifi.c",
                "main/wifi.h",
                "readme.md",
                "cmakelists.txt",
            ],
        }
    )

    result = FirmwareProjectValidator().validate(project)

    assert result.success is False
    assert "missing required project file: README.md" in result.errors
    assert "missing required project file: CMakeLists.txt" in result.errors
