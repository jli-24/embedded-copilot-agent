from __future__ import annotations

import copy
from collections.abc import Mapping

from pydantic import ValidationError

from embedded_copilot.supervisor.exceptions import SupervisorAnalysisError
from embedded_copilot.supervisor.models import SupervisorTask


_AGENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "FirmwareAgent": (
        "firmware",
        "固件",
        "code",
        "代码",
        "freertos",
        "esp-idf",
        "uart",
        "spi",
        "gpio",
        "wifi",
    ),
    "HardwareAgent": (
        "hardware",
        "硬件",
        "component",
        "组件",
        "mcu",
        "单片机",
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
        "pcb",
        "印制电路板",
        "电路板",
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
}
_AGENT_KEYWORDS["DebugAgent"] = (
    "debug",
    "error",
    "failure",
    "failed",
    "crash",
    "hard fault",
    "hardfault",
    "compile error",
    "communication error",
)
_AGENT_ALIASES = {
    "firmware": "FirmwareAgent",
    "firmwareagent": "FirmwareAgent",
    "hardware": "HardwareAgent",
    "hardwareagent": "HardwareAgent",
    "pcb": "PCBAgent",
    "pcbagent": "PCBAgent",
    "debug": "DebugAgent",
    "debugagent": "DebugAgent",
}
_CANONICAL_ORDER = ("FirmwareAgent", "HardwareAgent", "PCBAgent")
_DESIGN_KEYWORDS = ("design", "设计", "方案")
_PLATFORM_KEYWORDS = ("esp32", "stm32", "mcu", "单片机")
_SYSTEM_KEYWORDS = (
    "camera",
    "相机",
    "摄像头",
    "sensor",
    "传感器",
    "terminal",
    "终端",
)
_CONTROL_FIELDS = {
    "project_name",
    "required_agents",
    "constraints",
    "firmware_project",
    "hardware_plan",
    "knowledge_mode",
    "knowledge_documents",
    "knowledge_evidence",
    "knowledge_provenance",
    "_supervisor_knowledge",
}


class SupervisorRequirementAnalyzer:
    """Classify a request using deterministic, offline keyword rules."""

    def analyze(
        self,
        request: str,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> SupervisorTask:
        try:
            if metadata is not None and not isinstance(metadata, Mapping):
                raise TypeError("metadata must be a mapping")
            copied_metadata = copy.deepcopy(dict(metadata or {}))
            project_name = copied_metadata.pop("project_name", None)
            constraints = copied_metadata.pop("constraints", [])
            override_agents = copied_metadata.pop("required_agents", None)
            required_agents = (
                self._normalize_agent_override(override_agents)
                if override_agents is not None
                else self._detect_agents(request)
            )
            return SupervisorTask(
                request=request,
                project_name=project_name,
                required_agents=required_agents,
                constraints=constraints,
                metadata={
                    key: value
                    for key, value in copied_metadata.items()
                    if key not in _CONTROL_FIELDS
                },
            )
        except SupervisorAnalysisError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise SupervisorAnalysisError(
                "supervisor requirement analysis failed"
            ) from exc

    @staticmethod
    def _normalize_agent_override(value: object) -> list[str]:
        if not isinstance(value, list):
            raise SupervisorAnalysisError("required_agents must be a list")
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise SupervisorAnalysisError("required_agents values are invalid")
            canonical = _AGENT_ALIASES.get(item.strip().casefold())
            if canonical is None:
                raise SupervisorAnalysisError("required_agents contains an unknown agent")
            key = canonical.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(canonical)
        return normalized

    @staticmethod
    def _detect_agents(request: str) -> list[str]:
        if not isinstance(request, str):
            return []
        normalized = request.casefold()
        if (
            any(keyword in normalized for keyword in _DESIGN_KEYWORDS)
            and any(keyword in normalized for keyword in _PLATFORM_KEYWORDS)
            and any(keyword in normalized for keyword in _SYSTEM_KEYWORDS)
        ):
            selected = list(_CANONICAL_ORDER)
            if any(
                keyword in normalized
                for keyword in _AGENT_KEYWORDS["DebugAgent"]
            ):
                selected.append("DebugAgent")
            return selected

        matches: list[tuple[int, int, str]] = []
        for order, (agent_name, keywords) in enumerate(_AGENT_KEYWORDS.items()):
            positions = [normalized.find(keyword) for keyword in keywords]
            found = [position for position in positions if position >= 0]
            if found:
                matches.append((min(found), order, agent_name))
        matches.sort()
        return [agent_name for _, _, agent_name in matches]
