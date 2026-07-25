from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from embedded_copilot.input.models import UserAttachment
from embedded_copilot.schemas.result import ContractModel


DemoAgent = Literal["firmware", "hardware", "pcb", "debug"]


class DemoManifest(ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    request: str = Field(min_length=1, max_length=20_000)
    attachments: tuple[UserAttachment, ...] = Field(min_length=1, max_length=8)
    required_agents: tuple[DemoAgent, ...]

    @field_validator("required_agents")
    @classmethod
    def reject_duplicate_agents(
        cls,
        value: tuple[DemoAgent, ...],
    ) -> tuple[DemoAgent, ...]:
        if len(value) != len(set(value)):
            raise ValueError("demo agents must be unique")
        return value


def load_demo_manifest(path: Path) -> DemoManifest:
    if not isinstance(path, Path) or path.name != "manifest.json":
        raise ValueError("demo manifest path is invalid")
    try:
        payload = json.loads(path.read_bytes())
        return DemoManifest.model_validate(payload)
    except (OSError, ValueError, TypeError):
        raise ValueError("demo manifest is invalid") from None
