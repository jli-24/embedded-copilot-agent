from __future__ import annotations

from typing import Protocol, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from embedded_copilot.schemas.result import DebugResult, FirmwareResult


class LLMService(Protocol):
    def answer_knowledge(self, *, query: str, contexts: Sequence[str]) -> str: ...

    def generate_firmware(
        self,
        *,
        operation: str,
        request: str,
        code: str | None,
        language: str,
        platform: str,
    ) -> FirmwareResult: ...

    def analyze_debug(
        self,
        *,
        log: str,
        platform: str | None,
        evidence: Sequence[str],
    ) -> DebugResult: ...


class OfflineLLMService:
    """Honest deterministic fallback for the offline v0.1 workflow."""

    def answer_knowledge(self, *, query: str, contexts: Sequence[str]) -> str:
        if not contexts:
            return "没有在当前 Embedded Knowledge Base 中找到相关内容。"
        return contexts[0]

    def generate_firmware(
        self,
        *,
        operation: str,
        request: str,
        code: str | None,
        language: str,
        platform: str,
    ) -> FirmwareResult:
        lowered = request.lower()
        if operation == "generate" and "led" in lowered and (
            "freertos" in lowered or "任务" in request
        ):
            generated = """#include <stdbool.h>

#include "driver/gpio.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static void led_task(void *argument)
{
    const gpio_num_t led_gpio = (gpio_num_t)CONFIG_LED_GPIO;
    bool level = false;
    (void)argument;

    while (true) {
        level = !level;
        ESP_ERROR_CHECK(gpio_set_level(led_gpio, level));
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void app_main(void)
{
    const gpio_config_t config = {
        .pin_bit_mask = 1ULL << CONFIG_LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    ESP_ERROR_CHECK(gpio_config(&config));
    configASSERT(
        xTaskCreate(led_task, "led_task", 2048, NULL, 5, NULL) == pdPASS
    );
}
"""
            explanation = (
                "The task configures a caller-selected GPIO, toggles it without "
                "busy-waiting, and checks ESP-IDF and FreeRTOS return values."
            )
        elif operation == "explain" and code:
            generated = code
            explanation = (
                "Offline mode can preserve and summarize the supplied code, but "
                "a configured LLM is required for deeper project-specific analysis."
            )
        else:
            generated = code or ""
            explanation = (
                "Offline mode cannot safely produce arbitrary project-specific "
                "firmware without the exact MCU, SDK/HAL version, pins, and clocks."
            )
        return FirmwareResult(
            language=language,
            platform=platform,
            code=generated,
            explanation=explanation,
            limitations=[
                "This output has not been compiled or hardware tested.",
                "Confirm the MCU, board, SDK/HAL version, clocks, pins, and ownership.",
            ],
        )

    def analyze_debug(
        self,
        *,
        log: str,
        platform: str | None,
        evidence: Sequence[str],
    ) -> DebugResult:
        lowered = log.lower()
        if "guru meditation" in lowered:
            problem_type = "ESP32 Guru Meditation"
        elif "hardfault" in lowered or "hard fault" in lowered:
            problem_type = "STM32 HardFault"
        elif "error:" in lowered:
            problem_type = "Compiler Error"
        else:
            problem_type = "Serial Log"

        if "loadprohibited" in lowered:
            root_cause = [
                "LoadProhibited is consistent with an invalid memory read; "
                "the Backtrace and decoded source are required to confirm it."
            ]
        elif problem_type == "STM32 HardFault":
            root_cause = [
                "The fault class is observed, but stacked registers and fault "
                "status registers are required to identify the instruction cause."
            ]
        else:
            root_cause = [
                "The available excerpt is insufficient to identify one root cause."
            ]
        confidence = "medium" if "backtrace" in lowered and evidence else "low"
        return DebugResult(
            problem_type=problem_type,
            evidence=list(evidence),
            root_cause=root_cause,
            confidence=confidence,
            solution=[
                "Preserve the complete log and reproduce with the same firmware build.",
            ],
            next_steps=[
                "Provide the ELF/map file and decode addresses to source lines.",
                "Provide the exact MCU, SDK/HAL version, and reproduction conditions.",
            ],
        )


class LangChainLLMService:
    """Typed adapter around one configured LangChain chat model."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    def answer_knowledge(self, *, query: str, contexts: Sequence[str]) -> str:
        context = "\n\n".join(contexts)
        response = self._model.invoke(
            [
                SystemMessage(
                    content=(
                        "Answer only from the supplied embedded-engineering context. "
                        "If context is insufficient, say so explicitly."
                    )
                ),
                HumanMessage(content=f"Question: {query}\n\nContext:\n{context}"),
            ]
        )
        return str(response.content)

    def generate_firmware(
        self,
        *,
        operation: str,
        request: str,
        code: str | None,
        language: str,
        platform: str,
    ) -> FirmwareResult:
        structured = self._model.with_structured_output(FirmwareResult)
        response = structured.invoke(
            [
                SystemMessage(
                    content=(
                        "Return reviewable embedded firmware guidance. State all "
                        "hardware and SDK assumptions and never claim hardware testing."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Operation: {operation}\nLanguage: {language}\n"
                        f"Platform: {platform}\nRequest: {request}\n"
                        f"Code: {code or '<none>'}"
                    )
                ),
            ]
        )
        return FirmwareResult.model_validate(response)

    def analyze_debug(
        self,
        *,
        log: str,
        platform: str | None,
        evidence: Sequence[str],
    ) -> DebugResult:
        structured = self._model.with_structured_output(DebugResult)
        response = structured.invoke(
            [
                SystemMessage(
                    content=(
                        "Separate observed evidence from inferred root causes. "
                        "Use low confidence when decisive evidence is missing."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Platform: {platform or 'unknown'}\n"
                        f"Observed evidence: {list(evidence)}\nLog:\n{log}"
                    )
                ),
            ]
        )
        return DebugResult.model_validate(response)
