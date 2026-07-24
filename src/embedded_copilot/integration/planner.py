from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.input.models import AttachmentType
from embedded_copilot.integration.context import (
    EngineeringContext,
    IntegrationAgentName,
)


_AGENT_ORDER: tuple[IntegrationAgentName, ...] = (
    "FirmwareAgent",
    "HardwareAgent",
    "PCBAgent",
    "DebugAgent",
)
_ALIASES: dict[str, IntegrationAgentName] = {
    "firmware": "FirmwareAgent",
    "firmwareagent": "FirmwareAgent",
    "hardware": "HardwareAgent",
    "hardwareagent": "HardwareAgent",
    "pcb": "PCBAgent",
    "pcbagent": "PCBAgent",
    "debug": "DebugAgent",
    "debugagent": "DebugAgent",
}
_KEYWORDS: dict[IntegrationAgentName, tuple[str, ...]] = {
    "FirmwareAgent": (
        "firmware",
        "固件",
        "code",
        "代码",
        "driver",
        "hal",
        "esp-idf",
        "stm32",
        "freertos",
        "uart",
        "spi",
        "gpio",
        "wifi",
    ),
    "HardwareAgent": (
        "hardware",
        "硬件",
        "datasheet",
        "component",
        "组件",
        "mcu",
        "单片机",
        "chip",
        "sensor",
        "传感器",
        "camera",
        "相机",
        "摄像头",
        "power",
        "电源",
        "interface",
        "接口",
    ),
    "PCBAgent": (
        "kicad",
        "pcb",
        "印制电路板",
        "电路板",
        "board",
        "layout",
        "布局",
        "routing",
        "布线",
        "走线",
        "signal",
        "信号",
        "power integrity",
        "电源完整性",
        "grounding",
        "接地",
    ),
    "DebugAgent": (
        "debug",
        "error",
        "exception",
        "failure",
        "failed",
        "crash",
        "log",
        "hard fault",
        "hardfault",
        "compile error",
        "communication error",
    ),
}
_DESIGN_KEYWORDS = ("design", "设计", "方案")
_PLATFORM_KEYWORDS = ("esp32", "stm32", "mcu", "单片机")
_SYSTEM_KEYWORDS = ("camera", "相机", "摄像头", "sensor", "传感器", "terminal", "终端")


class IntegrationPlanner:
    """Select Agents with deterministic rules and no engineering conclusions."""

    def select_agents(
        self,
        context: EngineeringContext,
        *,
        required_agents: object | None = None,
        seed_agents: object | None = None,
    ) -> tuple[IntegrationAgentName, ...]:
        if not isinstance(context, EngineeringContext):
            raise ValueError("engineering context is invalid")
        if required_agents is not None:
            return self._normalize_required_agents(required_agents)

        selected = (
            set(self._normalize_required_agents(seed_agents))
            if seed_agents is not None
            else self._select_from_text(self._searchable_input(context))
        )
        if seed_agents is not None:
            selected.update(
                self._select_from_text(
                    self._searchable_input(context, include_request=False)
                )
            )

        if context.datasheet_model is not None:
            selected.add("HardwareAgent")
        if context.pcb_model is not None:
            selected.add("PCBAgent")
        if context.input_context is not None:
            attachment_routes = {
                AttachmentType.SOURCE_CODE: "FirmwareAgent",
                AttachmentType.EDA: "PCBAgent",
                AttachmentType.LOG: "DebugAgent",
            }
            for attachment in context.input_context.attachments:
                agent_name = attachment_routes.get(attachment.media_type)
                if agent_name is not None:
                    selected.add(agent_name)
        return tuple(name for name in _AGENT_ORDER if name in selected)

    @staticmethod
    def _select_from_text(
        searchable: str,
    ) -> set[IntegrationAgentName]:
        selected = {
            agent_name
            for agent_name, keywords in _KEYWORDS.items()
            if any(keyword in searchable for keyword in keywords)
        }
        if (
            any(keyword in searchable for keyword in _DESIGN_KEYWORDS)
            and any(keyword in searchable for keyword in _PLATFORM_KEYWORDS)
            and any(keyword in searchable for keyword in _SYSTEM_KEYWORDS)
        ):
            selected.update(("FirmwareAgent", "HardwareAgent", "PCBAgent"))
        return selected

    @staticmethod
    def _normalize_required_agents(
        value: object,
    ) -> tuple[IntegrationAgentName, ...]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ValueError("required_agents must be a sequence")
        selected: set[IntegrationAgentName] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("required_agents values are invalid")
            agent_name = _ALIASES.get(item.strip().casefold())
            if agent_name is None:
                raise ValueError("required_agents contains an unknown agent")
            selected.add(agent_name)
        return tuple(name for name in _AGENT_ORDER if name in selected)

    @staticmethod
    def _searchable_input(
        context: EngineeringContext,
        *,
        include_request: bool = True,
    ) -> str:
        values = [context.request] if include_request else []
        input_context = context.input_context
        if input_context is not None:
            values.append(input_context.text)
            for attachment in input_context.attachments:
                values.extend((attachment.filename, attachment.media_type.value))
                values.extend(
                    str(value)
                    for value in attachment.metadata.values()
                    if value is not None
                )
        return " ".join(values).casefold()
