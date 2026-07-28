from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

import embedded_copilot.coding_runtime as public_runtime
from embedded_copilot.coding_runtime import (
    BuildAnalysisRequest,
    CodeFileInput,
    CodingIntelligencePort,
    CodingRuntime,
    DiffReviewRequest,
    FrozenCodeContextSnapshot,
    HardwareSoftwareFusionRequest,
    PinFunctionCandidate,
    ProjectAnalysisRequest,
    create_coding_runtime,
)
from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    DatasheetContext,
    EngineeringContextResponse,
    EngineeringContextSummary,
    FileContext,
)

CONTEXT_ID = "context:0123456789abcdef01234567"


def _runtime() -> CodingIntelligencePort:
    runtime = create_coding_runtime()
    assert isinstance(runtime, CodingRuntime)
    return runtime.coding_port()


def _project(*files: CodeFileInput):
    return _runtime().analyze_project(
        ProjectAnalysisRequest(context_id=CONTEXT_ID, files=files)
    )


def test_snapshot_is_frozen_and_fingerprint_is_stable() -> None:
    files = (
        CodeFileInput(
            path="src/main.c",
            content="#include <stdint.h>\n#define LED 5\nint main(void) { return 0; }\n",
        ),
        CodeFileInput(path="CMakeLists.txt", content="project(sample)\n"),
    )

    first = _project(*files).snapshot
    second = _project(*reversed(files)).snapshot

    assert isinstance(first, FrozenCodeContextSnapshot)
    assert first.schema_version == "1.0"
    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.files == second.files
    assert not hasattr(first.files[0], "content")
    with pytest.raises(ValidationError):
        first.context_id = "context:ffffffffffffffffffffffff"  # type: ignore[misc]
    payload = first.model_dump(mode="python")
    payload["project_type"] = "ESP_IDF"
    with pytest.raises(ValidationError, match="snapshot_fingerprint"):
        FrozenCodeContextSnapshot.model_validate(payload)


def test_c_parser_extracts_symbols_includes_macros_and_gpio_access() -> None:
    response = _project(
        CodeFileInput(
            path="Core/Src/main.c",
            content=(
                '#include "main.h"\n'
                "#define STATUS_LED GPIO_PIN_5\n"
                "struct Device { int state; };\n"
                "static void toggle(void) {\n"
                "  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);\n"
                "}\n"
            ),
        )
    )

    assert {(item.kind, item.name) for item in response.snapshot.symbols} >= {
        ("include", "main.h"),
        ("macro", "STATUS_LED"),
        ("struct", "Device"),
        ("function", "toggle"),
    }
    assert response.snapshot.dependencies[0].name == "main.h"
    access = response.snapshot.files[0].hardware_accesses[0]
    assert (access.resource, access.operation) == ("PA5", "digital_write")


def test_cpp_and_python_parsers_extract_symbols_and_dependencies() -> None:
    response = _project(
        CodeFileInput(
            path="src/controller.cpp",
            content=(
                "#include <vector>\n"
                "class Controller { public: void run(); };\n"
                "void Controller::run() {}\n"
            ),
        ),
        CodeFileInput(
            path="tools/check.py",
            content=(
                "import json\n"
                "from pathlib import Path\n"
                "class Inspector: pass\n"
                "def inspect_project(): return None\n"
            ),
        ),
    )

    symbols = {(item.kind, item.name) for item in response.snapshot.symbols}
    assert ("class", "Controller") in symbols
    assert ("function", "run") in symbols
    assert ("class", "Inspector") in symbols
    assert ("function", "inspect_project") in symbols
    assert {item.name for item in response.snapshot.dependencies} >= {
        "vector",
        "json",
        "pathlib",
    }
    assert response.snapshot.language == "MIXED"


def test_project_analyzer_recognizes_stm32_and_esp_idf() -> None:
    stm32 = _project(
        CodeFileInput(path="project.ioc", content="ProjectManager.ProjectName=demo\n"),
        CodeFileInput(path="Core/Src/main.c", content="int main(void) {}\n"),
        CodeFileInput(path="Drivers/CMSIS/readme.txt", content="CMSIS\n"),
        CodeFileInput(path="startup/startup_stm32.s", content="Reset_Handler:\n"),
    )
    esp_idf = _project(
        CodeFileInput(
            path="CMakeLists.txt",
            content="include($ENV{IDF_PATH}/tools/cmake/project.cmake)\nproject(app)\n",
        ),
        CodeFileInput(path="main/main.c", content="void app_main(void) {}\n"),
    )

    assert stm32.project_summary.project_type == "STM32CUBEMX"
    assert "STM32" in stm32.project_summary.frameworks
    assert esp_idf.project_summary.project_type == "ESP_IDF"
    assert esp_idf.project_summary.build_system == "CMAKE"


def test_project_analyzer_recognizes_arduino_zephyr_and_freertos() -> None:
    arduino = _project(
        CodeFileInput(path="sketch.ino", content="void setup() {} void loop() {}\n")
    )
    zephyr = _project(
        CodeFileInput(path="prj.conf", content="CONFIG_GPIO=y\n"),
        CodeFileInput(
            path="CMakeLists.txt",
            content="find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})\n",
        ),
        CodeFileInput(
            path="src/main.c",
            content="#include <FreeRTOS.h>\nint main(void) { return 0; }\n",
        ),
    )

    assert arduino.project_summary.project_type == "ARDUINO"
    assert arduino.project_summary.build_system == "ARDUINO"
    assert zephyr.project_summary.project_type == "ZEPHYR"
    assert zephyr.project_summary.frameworks == ("ZEPHYR", "FREERTOS")


@pytest.mark.parametrize("compiler", ("GCC", "CLANG", "ARM_NONE_EABI_GCC"))
def test_build_analyzer_parses_supported_compiler_diagnostics(compiler: str) -> None:
    response = _runtime().analyze_build(
        BuildAnalysisRequest(
            compiler=compiler,
            log="src/main.c:42:7: error: use of undeclared identifier 'value'\n",
        )
    )

    issue = response.issues[0]
    assert (issue.error_type, issue.file, issue.line) == (
        "COMPILER_ERROR",
        "src/main.c",
        42,
    )
    assert issue.evidence.startswith("observed:")
    assert "modify" not in issue.suggestion.casefold()


def test_diff_review_returns_only_unverified_candidates() -> None:
    review = _runtime().review_diff(
        DiffReviewRequest(
            diff=(
                "diff --git a/include/api.h b/include/api.h\n"
                "--- a/include/api.h\n+++ b/include/api.h\n"
                "@@ -1 +1,3 @@\n"
                "-int read_value(void);\n+int read_value(int channel);\n"
                "+HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);\n"
                "+HAL_SPI_Init(&hspi1);\n"
            )
        )
    )

    assert review.candidate_semantics == "unverified"
    assert {item.category for item in review.candidates} >= {
        "API_CHANGE",
        "MCU_RESOURCE",
        "PERIPHERAL_CONFIGURATION",
    }
    assert not hasattr(review, "patch")
    assert not hasattr(review, "commit")


def test_datasheet_code_fusion_returns_pin_conflict_candidate() -> None:
    project = _project(
        CodeFileInput(
            path="Core/Src/main.c",
            content=(
                "void toggle(void) {"
                "HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);}"
            ),
        )
    )
    context = EngineeringContextResponse(
        context_summary=EngineeringContextSummary(
            context_id=CONTEXT_ID,
            task_intent="Review GPIO and datasheet candidates.",
            files=(
                FileContext(
                    file_id="file:datasheet-1",
                    document_type=ContextDocumentType.DATASHEET,
                    page_count=32,
                ),
            ),
            datasheets=(
                DatasheetContext(
                    file_id="file:datasheet-1",
                    component_candidate=ComponentContextCandidate(family="STM32"),
                ),
            ),
        )
    )

    response = _runtime().analyze_hardware_software(
        HardwareSoftwareFusionRequest(
            snapshot=project.snapshot,
            engineering_context=context,
            pin_candidates=(
                PinFunctionCandidate(
                    reference_id="file:datasheet-1",
                    pin="PA5",
                    function="SPI_CLK",
                ),
            ),
        )
    )

    assert response.candidate_semantics == "unverified"
    candidate = response.conflict_candidates[0]
    assert (candidate.pin, candidate.candidate_function) == ("PA5", "SPI_CLK")
    assert candidate.reference_id == "file:datasheet-1"
    assert "candidate" in candidate.description.casefold()


def test_inputs_are_bounded_and_runtime_exposes_no_mutation_capability() -> None:
    with pytest.raises(ValidationError):
        CodeFileInput(path="../private/main.c", content="int main(void) {}")
    with pytest.raises(ValidationError):
        CodeFileInput(path="main.exe", content="binary")

    with pytest.raises(TypeError, match="composition factory"):
        CodingRuntime(object())
    assert {
        name
        for name, value in CodingRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"coding_port"}
    assert tuple(
        inspect.signature(CodingIntelligencePort.analyze_project).parameters
    ) == (
        "self",
        "request",
    )
    for capability in ("write", "patch", "apply", "execute", "generate", "commit"):
        assert not hasattr(_runtime(), capability)

    assert "CodingRuntime" in public_runtime.__all__
    assert "create_coding_runtime" in public_runtime.__all__
