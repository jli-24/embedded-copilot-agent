from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.firmware.review.analyzer import (
    FirmwareReviewAnalyzer,
    FirmwareReviewError,
)
from embedded_copilot.firmware.review.models import FirmwareReviewResult, FirmwareSource


def _source(filename: str, source_id: str, text: str) -> FirmwareSource:
    language = "C++" if filename.endswith(".cpp") else "C"
    return FirmwareSource(
        filename=filename,
        source_id=source_id,
        language=language,
        text=text,
    )


def test_firmware_review_extracts_architecture_and_deterministic_rules() -> None:
    sources = (
        _source(
            "main.c",
            "attachment:main",
            """
            void camera_init(void);
            void wifi_init(void);
            static void worker(void *arg) {
                for (;;) { do_work(); }
            }
            void app_main(void) {
                camera_init();
                wifi_init();
                xTaskCreate(worker, "worker", 2048, 0, 5, 0);
            }
            """,
        ),
        _source(
            "camera.c",
            "attachment:camera",
            """
            void camera_init(void) {
                camera_config_t config = { .pin_d0 = GPIO_NUM_8 };
                gpio_config_t io = { .pin_bit_mask = 1ULL << GPIO_NUM_8 };
                gpio_config(&io);
            }
            """,
        ),
        _source(
            "memory.c",
            "attachment:memory",
            """
            void IRAM_ATTR gpio_isr_handler(void *arg) {
                void *buffer = malloc(16);
                vTaskDelay(1);
            }
            void use_gpio(void) { gpio_set_level(GPIO_NUM_5, 1); }
            """,
        ),
    )

    first = FirmwareReviewAnalyzer().analyze(sources)
    second = FirmwareReviewAnalyzer().analyze(sources)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.platform == "ESP32"
    assert first.framework == "ESP-IDF"
    assert first.entrypoints == ("app_main",)
    assert first.initialization_flow == (
        "app_main -> camera_init",
        "app_main -> wifi_init",
    )
    assert first.tasks[0].function == "worker"
    assert first.tasks[0].infinite_loop is True
    assert first.tasks[0].has_blocking_call is False
    rules = {finding.rule_id: finding for finding in first.findings}
    assert rules["freertos-task-starvation"].severity == "high"
    assert rules["isr-blocking-call"].severity == "high"
    assert rules["isr-heap-allocation"].severity == "high"
    assert rules["unchecked-allocation"].severity == "medium"
    assert rules["gpio-without-initialization"].severity == "medium"
    assert any(
        item.pin == "GPIO8" and item.role == "Camera" and item.initialized
        for item in first.gpio_assignments
    )


def test_firmware_review_masks_comments_and_strings() -> None:
    result = FirmwareReviewAnalyzer().analyze(
        (
            _source(
                "main.c",
                "attachment:main",
                """
                // xTaskCreate(fake_task, "fake", 1, 0, 1, 0);
                const char *text = "gpio_set_level(GPIO_NUM_9, 1)";
                void app_main(void) { real_init(); }
                """,
            ),
        )
    )

    assert result.entrypoints == ("app_main",)
    assert result.tasks == ()
    assert result.gpio_assignments == ()


def test_firmware_review_associates_gpio_initialization_with_the_configured_pin() -> None:
    result = FirmwareReviewAnalyzer().analyze(
        (
            _source(
                "main.c",
                "attachment:main",
                """
                void gpio_init(void) {
                    gpio_config_t io = { .pin_bit_mask = 1ULL << GPIO_NUM_8 };
                    gpio_config(&io);
                }
                void drive_output(void) { gpio_set_level(GPIO_NUM_5, 1); }
                """,
            ),
        )
    )

    gpio5 = next(item for item in result.gpio_assignments if item.pin == "GPIO5")
    assert gpio5.initialized is False
    assert any(
        item.rule_id == "gpio-without-initialization" and item.line == gpio5.line
        for item in result.findings
    )


def test_firmware_review_does_not_classify_task_callback_as_isr() -> None:
    result = FirmwareReviewAnalyzer().analyze(
        (
            _source(
                "callbacks.c",
                "attachment:callbacks",
                "void event_callback(void *arg) { vTaskDelay(1); }",
            ),
        )
    )

    assert result.interrupts == ()
    assert all(item.rule_id != "isr-blocking-call" for item in result.findings)


def test_firmware_review_rejects_unbalanced_source_without_leaking_it() -> None:
    with pytest.raises(FirmwareReviewError) as captured:
        FirmwareReviewAnalyzer().analyze(
            (
                _source(
                    "private.c",
                    "attachment:private",
                    "void app_main(void) { PRIVATE_SOURCE_SENTINEL",
                ),
            )
        )

    assert "PRIVATE_SOURCE_SENTINEL" not in str(captured.value)
    assert "private.c" not in str(captured.value)


def test_firmware_review_models_reject_filesystem_paths() -> None:
    with pytest.raises(ValidationError):
        FirmwareReviewResult(
            files=(r"C:\private\main.c",),
            source_ids=("attachment:main",),
        )

    with pytest.raises(ValidationError):
        FirmwareSource(
            filename="main.c",
            source_id=r"C:\private\main.c",
            language="C",
            text="void app_main(void) {}",
        )
