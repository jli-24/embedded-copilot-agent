from __future__ import annotations

from collections.abc import Sequence

from embedded_copilot.firmware.exceptions import FirmwarePlanningError
from embedded_copilot.firmware.intelligence.analyzer import FirmwareRequirementAnalysis
from embedded_copilot.firmware.knowledge.models import FirmwareDocument
from embedded_copilot.firmware.planner.models import FirmwarePlan


_FILE_BY_PERIPHERAL = {
    "wifi": "wifi.c",
    "camera": "camera.c",
    "spi": "spi.c",
    "adc": "adc.c",
}


class FirmwarePlanner:
    def plan(
        self,
        analysis: FirmwareRequirementAnalysis,
        documents: Sequence[FirmwareDocument],
    ) -> FirmwarePlan:
        if analysis.platform is None:
            raise FirmwarePlanningError("firmware platform is required for planning")

        files = ["main.c"]
        for peripheral in analysis.peripherals:
            filename = _FILE_BY_PERIPHERAL.get(peripheral.casefold())
            if filename is not None and filename not in files:
                files.append(filename)

        dependencies = [analysis.framework] if analysis.framework is not None else []
        if documents:
            references = ", ".join(
                f"{document.title} ({document.id})" for document in documents
            )
            rationale = (
                "Deterministic rules selected the components and files. "
                f"Retrieved firmware knowledge: {references}."
            )
        else:
            rationale = (
                "Deterministic rules selected the components and files; "
                "no firmware knowledge documents matched, so the plan is unverified."
            )
        return FirmwarePlan(
            platform=analysis.platform,
            framework=analysis.framework,
            components=list(analysis.features),
            peripherals=list(analysis.peripherals),
            files=files,
            dependencies=dependencies,
            rationale=rationale,
        )
