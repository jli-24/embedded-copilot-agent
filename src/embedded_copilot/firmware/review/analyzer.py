from __future__ import annotations

import re
from dataclasses import dataclass

from embedded_copilot.firmware.review.lexer import FirmwareLexError, mask_non_code
from embedded_copilot.firmware.review.models import (
    FirmwareFinding,
    FirmwareFunction,
    FirmwareGPIOAssignment,
    FirmwareReviewResult,
    FirmwareSource,
    FirmwareTaskEvidence,
)
from embedded_copilot.firmware.review.rules import finding, finding_sort_key


class FirmwareReviewError(RuntimeError):
    """Safe firmware review failure."""


_FUNCTION = re.compile(
    r"(?:^|\n)\s*(?:[A-Za-z_]\w*\s+|[A-Za-z_]\w*\s*\*\s*)+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_CONTROL_NAMES = frozenset({"if", "for", "while", "switch", "sizeof", "return"})
_BLOCKING_CALLS = frozenset(
    {
        "vTaskDelay",
        "vTaskDelayUntil",
        "xQueueReceive",
        "xSemaphoreTake",
        "ulTaskNotifyTake",
        "taskYIELD",
    }
)
_ALLOCATION_CALLS = frozenset({"malloc", "calloc", "realloc", "heap_caps_malloc"})
_INIT_CALL = re.compile(r"(?:^init_|_init$|^MX_.*_Init$|^HAL_.*_Init$)", re.I)
_GPIO = re.compile(r"\bGPIO_(?:NUM_|PIN_)?(\d+)\b")


@dataclass(frozen=True, slots=True)
class _ParsedFunction:
    model: FirmwareFunction
    source_id: str
    signature: str
    body: str
    body_start: int


class FirmwareReviewAnalyzer:
    def analyze(
        self,
        sources: tuple[FirmwareSource, ...],
    ) -> FirmwareReviewResult:
        if not isinstance(sources, tuple) or not sources:
            raise FirmwareReviewError("Firmware review input is invalid")
        try:
            parsed: list[_ParsedFunction] = []
            masked_sources: list[tuple[FirmwareSource, str]] = []
            for source in sources:
                if not isinstance(source, FirmwareSource):
                    raise TypeError("invalid source")
                masked = mask_non_code(source.text)
                masked_sources.append((source, masked))
                parsed.extend(self._functions(source, masked))
            return self._result(sources, tuple(masked_sources), tuple(parsed))
        except FirmwareReviewError:
            raise
        except (FirmwareLexError, TypeError, ValueError):
            raise FirmwareReviewError("Firmware static analysis failed") from None

    def _result(
        self,
        sources: tuple[FirmwareSource, ...],
        masked_sources: tuple[tuple[FirmwareSource, str], ...],
        parsed: tuple[_ParsedFunction, ...],
    ) -> FirmwareReviewResult:
        functions = tuple(item.model for item in parsed)
        by_name = {item.model.name: item for item in parsed}
        entrypoints = tuple(
            name for name in ("main", "app_main") if name in by_name
        )
        initialization_flow = tuple(
            f"{entry} -> {call}"
            for entry in entrypoints
            for call in by_name[entry].model.calls
            if _INIT_CALL.search(call)
        )
        tasks, task_findings = self._tasks(parsed, by_name)
        interrupts, interrupt_findings = self._interrupts(parsed)
        allocations, allocation_findings = self._allocations(parsed)
        gpio, gpio_findings = self._gpio(masked_sources)
        findings = sorted(
            [
                *task_findings,
                *interrupt_findings,
                *allocation_findings,
                *gpio_findings,
            ],
            key=finding_sort_key,
        )
        all_text = "\n".join(masked for _, masked in masked_sources)
        platform = (
            "ESP32"
            if re.search(r"\b(?:GPIO_NUM_|esp_|gpio_config|IRAM_ATTR)\b", all_text)
            else "STM32"
            if re.search(r"\b(?:HAL_|GPIO_PIN_)\w*", all_text)
            else None
        )
        framework = "ESP-IDF" if platform == "ESP32" else "HAL" if platform == "STM32" else None
        peripherals = tuple(
            name
            for name, pattern in (
                ("GPIO", r"\b(?:gpio_|HAL_GPIO_)"),
                ("UART", r"\b(?:uart_|HAL_UART_)"),
                ("SPI", r"\b(?:spi_|HAL_SPI_)"),
                ("I2C", r"\b(?:i2c_|HAL_I2C_)"),
                ("Camera", r"\b(?:camera_|esp_camera_)"),
            )
            if re.search(pattern, all_text, re.I)
        )
        return FirmwareReviewResult(
            files=tuple(source.filename for source in sources),
            platform=platform,
            framework=framework,
            entrypoints=entrypoints,
            functions=functions,
            initialization_flow=initialization_flow,
            tasks=tuple(tasks),
            interrupts=tuple(interrupts),
            allocations=tuple(allocations),
            peripherals=peripherals,
            gpio_assignments=tuple(gpio),
            findings=tuple(findings),
            limitations=(
                "Macro expansion, conditional compilation, types, and linking were not evaluated.",
            ),
            source_ids=tuple(source.source_id for source in sources),
        )

    @staticmethod
    def _functions(source: FirmwareSource, masked: str) -> list[_ParsedFunction]:
        result: list[_ParsedFunction] = []
        for match in _FUNCTION.finditer(masked):
            name = match.group("name")
            if name in _CONTROL_NAMES:
                continue
            opening = match.end() - 1
            closing = _matching_brace(masked, opening)
            body = masked[opening + 1 : closing]
            calls = tuple(
                candidate
                for candidate in dict.fromkeys(_CALL.findall(body))
                if candidate not in _CONTROL_NAMES and candidate != name
            )
            line = masked.count("\n", 0, match.start()) + 1
            result.append(
                _ParsedFunction(
                    model=FirmwareFunction(
                        name=name,
                        filename=source.filename,
                        line=line,
                        calls=calls,
                    ),
                    source_id=source.source_id,
                    signature=masked[match.start() : opening],
                    body=body,
                    body_start=opening + 1,
                )
            )
        return result

    @staticmethod
    def _tasks(
        parsed: tuple[_ParsedFunction, ...],
        by_name: dict[str, _ParsedFunction],
    ) -> tuple[list[FirmwareTaskEvidence], list[FirmwareFinding]]:
        tasks: list[FirmwareTaskEvidence] = []
        findings: list[FirmwareFinding] = []
        task_names: list[str] = []
        for caller in parsed:
            task_names.extend(
                re.findall(
                    r"\bxTaskCreate(?:PinnedToCore)?\s*\(\s*([A-Za-z_]\w*)",
                    caller.body,
                )
            )
        for name in dict.fromkeys(task_names):
            task = by_name.get(name)
            if task is None:
                continue
            infinite = bool(
                re.search(r"\bfor\s*\(\s*;\s*;\s*\)|\bwhile\s*\(\s*(?:1|true)\s*\)", task.body)
            )
            has_blocking = any(
                re.search(rf"\b{re.escape(call)}\s*\(", task.body)
                for call in _BLOCKING_CALLS
            )
            evidence = FirmwareTaskEvidence(
                function=name,
                source_id=task.source_id,
                line=task.model.line,
                infinite_loop=infinite,
                has_blocking_call=has_blocking,
            )
            tasks.append(evidence)
            if infinite and not has_blocking:
                findings.append(
                    finding(
                        rule_id="freertos-task-starvation",
                        severity="high",
                        description="FreeRTOS task has an infinite loop without an observed blocking or yield call.",
                        recommendation="Add a bounded blocking wait, notification, queue receive, delay, or explicit yield.",
                        source_id=task.source_id,
                        filename=task.model.filename,
                        line=task.model.line,
                    )
                )
        return tasks, findings

    @staticmethod
    def _interrupts(
        parsed: tuple[_ParsedFunction, ...],
    ) -> tuple[list[str], list[FirmwareFinding]]:
        interrupts: list[str] = []
        findings: list[FirmwareFinding] = []
        for function in parsed:
            is_interrupt = bool(
                re.search(r"IRAM_ATTR", function.signature)
                or re.search(r"(?:isr|irqhandler)", function.model.name, re.I)
            )
            if not is_interrupt:
                continue
            interrupts.append(
                f"{function.model.name}@{function.source_id}#line:{function.model.line}"
            )
            for call in function.model.calls:
                if call in _BLOCKING_CALLS:
                    findings.append(
                        finding(
                            rule_id="isr-blocking-call",
                            severity="high",
                            description="Interrupt context calls a blocking task-context API.",
                            recommendation="Use an ISR-safe API and defer blocking work to a task.",
                            source_id=function.source_id,
                            filename=function.model.filename,
                            line=function.model.line,
                        )
                    )
                if call in _ALLOCATION_CALLS:
                    findings.append(
                        finding(
                            rule_id="isr-heap-allocation",
                            severity="high",
                            description="Interrupt context performs heap allocation.",
                            recommendation="Preallocate memory and keep interrupt work bounded.",
                            source_id=function.source_id,
                            filename=function.model.filename,
                            line=function.model.line,
                        )
                    )
        return interrupts, findings

    @staticmethod
    def _allocations(
        parsed: tuple[_ParsedFunction, ...],
    ) -> tuple[list[str], list[FirmwareFinding]]:
        allocations: list[str] = []
        findings: list[FirmwareFinding] = []
        pattern = re.compile(
            r"\b([A-Za-z_]\w*)\s*=\s*(?:\([^;]+\)\s*)?"
            r"(malloc|calloc|realloc|heap_caps_malloc)\s*\("
        )
        for function in parsed:
            for match in pattern.finditer(function.body):
                variable, call = match.groups()
                line = function.model.line + function.body.count("\n", 0, match.start())
                allocations.append(
                    f"{function.model.name}:{call}@{function.source_id}#line:{line}"
                )
                remainder = function.body[match.end() :]
                checked = bool(
                    re.search(
                        rf"\bif\s*\(\s*(?:!\s*{re.escape(variable)}|{re.escape(variable)}\s*(?:==|!=)\s*(?:NULL|nullptr|0))",
                        remainder,
                    )
                )
                if not checked:
                    findings.append(
                        finding(
                            rule_id="unchecked-allocation",
                            severity="medium",
                            description="Heap allocation result has no observed null check.",
                            recommendation="Check the allocation result before use and define the failure path.",
                            source_id=function.source_id,
                            filename=function.model.filename,
                            line=line,
                        )
                    )
        return allocations, findings

    @staticmethod
    def _gpio(
        masked_sources: tuple[tuple[FirmwareSource, str], ...],
    ) -> tuple[list[FirmwareGPIOAssignment], list[FirmwareFinding]]:
        assignments: list[FirmwareGPIOAssignment] = []
        findings: list[FirmwareFinding] = []
        for source, masked in masked_sources:
            initialized_pins = _initialized_gpio_pins(masked)
            for line_number, line in enumerate(masked.splitlines(), start=1):
                pins = _GPIO.findall(line)
                if not pins:
                    continue
                role = _gpio_role(line)
                if role is None:
                    continue
                for number in pins:
                    assignment = FirmwareGPIOAssignment(
                        pin=f"GPIO{number}",
                        role=role,
                        source_id=source.source_id,
                        line=line_number,
                        initialized=number in initialized_pins,
                    )
                    assignments.append(assignment)
                    if number not in initialized_pins:
                        findings.append(
                            finding(
                                rule_id="gpio-without-initialization",
                                severity="medium",
                                description="GPIO use has no observed initialization in the source file.",
                                recommendation="Initialize direction, mode, pull configuration, and ownership before use.",
                                source_id=source.source_id,
                                filename=source.filename,
                                line=line_number,
                            )
                        )
        by_pin: dict[str, list[FirmwareGPIOAssignment]] = {}
        for assignment in assignments:
            by_pin.setdefault(assignment.pin, []).append(assignment)
        for pin, values in by_pin.items():
            roles = {item.role for item in values}
            if len(roles) <= 1:
                continue
            first = values[0]
            findings.append(
                finding(
                    rule_id="gpio-incompatible-roles",
                    severity="high",
                    description=f"{pin} is assigned multiple firmware roles: {', '.join(sorted(roles))}.",
                    recommendation="Assign unique GPIO ownership or document a verified time-multiplexing design.",
                    source_id=first.source_id,
                    filename=next(source.filename for source, _ in masked_sources if source.source_id == first.source_id),
                    line=first.line,
                )
            )
        return assignments, findings


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced function body")


def _gpio_role(line: str) -> str | None:
    if re.search(r"\.pin_d\d+|camera", line, re.I):
        return "Camera"
    if re.search(r"flash", line, re.I):
        return "Flash"
    if re.search(r"gpio_set_level|HAL_GPIO_WritePin", line):
        return "GPIO output"
    if re.search(r"uart", line, re.I):
        return "UART"
    if re.search(r"spi", line, re.I):
        return "SPI"
    if re.search(r"i2c", line, re.I):
        return "I2C"
    return None


def _initialized_gpio_pins(masked: str) -> set[str]:
    configured: dict[str, set[str]] = {}
    for match in re.finditer(
        r"\bgpio_config_t\s+([A-Za-z_]\w*)\s*=\s*\{(?P<body>.*?)\}\s*;",
        masked,
        re.S,
    ):
        configured.setdefault(match.group(1), set()).update(
            _GPIO.findall(match.group("body"))
        )
    for match in re.finditer(
        r"\b([A-Za-z_]\w*)\s*\.\s*(?:pin_bit_mask|Pin)\s*=\s*(?P<value>[^;]+);",
        masked,
    ):
        configured.setdefault(match.group(1), set()).update(
            _GPIO.findall(match.group("value"))
        )

    initialized: set[str] = set()
    for variable in re.findall(
        r"\bgpio_config\s*\(\s*&?\s*([A-Za-z_]\w*)\s*\)",
        masked,
    ):
        initialized.update(configured.get(variable, set()))
    for variable in re.findall(
        r"\bHAL_GPIO_Init\s*\([^,]+,\s*&\s*([A-Za-z_]\w*)\s*\)",
        masked,
    ):
        initialized.update(configured.get(variable, set()))
    return initialized
