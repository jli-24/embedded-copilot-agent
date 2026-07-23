from __future__ import annotations

from collections.abc import Mapping

from pydantic import Field, field_validator

from embedded_copilot.firmware.models import FirmwareRequest
from embedded_copilot.schemas.result import ContractModel


class FirmwarePlan(ContractModel):
    project_name: str | None = Field(default=None, min_length=1)
    platform: str = Field(min_length=1)
    framework: str | None = Field(default=None, min_length=1)
    components: list[str] = Field(default_factory=list)
    peripherals: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @field_validator(
        "project_name",
        "platform",
        "framework",
        "rationale",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    def to_firmware_request(
        self,
        *,
        requirement: str,
        metadata: Mapping[str, object] | None = None,
    ) -> FirmwareRequest:
        request_metadata = {
            **dict(metadata or {}),
            "planned_components": list(self.components),
            "planned_files": list(self.files),
            "planned_dependencies": list(self.dependencies),
            "planning_rationale": self.rationale,
        }
        if self.project_name is not None:
            request_metadata["project_name"] = self.project_name
        return FirmwareRequest(
            requirement=requirement,
            platform=self.platform,
            framework=self.framework,
            peripherals=list(self.peripherals),
            metadata=request_metadata,
        )
